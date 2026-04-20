"""Regression tests for BEC-46: Optuna study reload must tolerate a narrowed
categorical search space (e.g., `hidden_size: [64, 96, 128]` shrunk to
`[64, 96]` via a per-cluster override).

Before the fix, reusing a persisted study whose trials used a value that is
no longer in the current categorical choices raised either
`ValueError: '<v>' not in (...)` on the next suggestion or
`ValueError: CategoricalDistribution does not support dynamic value space.`

The fix bumps the study name when an incompatibility is detected so that a
fresh study is created without discarding history for clusters that still
match the original categorical space.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import optuna
import pytest

from src.training.optimize import (
    _categorical_search_space,
    _categorical_space_signature,
    _resolve_cluster_study_name,
    _study_has_incompatible_categorical_values,
)


@pytest.fixture
def sqlite_storage() -> str:
    """Ephemeral SQLite-backed Optuna storage URL.

    Using a file-based sqlite keeps the test deterministic and lets multiple
    `optuna.load_study` calls see the same persisted trials the way the
    Postgres-backed pipeline does at runtime.
    """
    with tempfile.TemporaryDirectory() as tmp:
        yield f"sqlite:///{Path(tmp) / 'optuna.db'}"


def _seed_study_with_trial(storage: str, study_name: str, hidden_size: int) -> None:
    """Create a study and run one trial that samples `hidden_size` from a
    categorical space containing the given value.

    This mimics what happens when BEC-42 had not yet narrowed the search
    space: the study is persisted with `hidden_size=128` baked into its
    categorical distribution.
    """
    study = optuna.create_study(
        study_name=study_name,
        storage=storage,
        direction="maximize",
    )

    def objective(trial: optuna.Trial) -> float:
        # Full (pre-BEC-42) categorical space.
        value = trial.suggest_categorical("hidden_size", [64, 96, 128])
        # Force the scheduled value so the regression covers the specific
        # case the production logs flagged.
        assert value == hidden_size
        return float(value)

    study.enqueue_trial({"hidden_size": hidden_size})
    study.optimize(objective, n_trials=1)


def test_categorical_search_space_filters_out_continuous_ranges() -> None:
    """Only list-valued entries count; continuous `{low, high}` dicts can be
    resized without triggering Optuna's dynamic-value-space check.
    """
    search_space = {
        "hidden_size": [64, 96],
        "learning_rate": {"low": 1e-4, "high": 1e-2, "log": True},
        "sequence_length": [10, 20, 30],
    }

    assert _categorical_search_space(search_space) == {
        "hidden_size": [64, 96],
        "sequence_length": [10, 20, 30],
    }


def test_categorical_space_signature_is_stable_and_order_independent() -> None:
    """The signature must be the same regardless of dict / list ordering so
    that two runs of the same config hit the same study.
    """
    sig_a = _categorical_space_signature(
        {
            "hidden_size": [64, 96],
            "batch_size": [64, 128, 256],
        }
    )
    sig_b = _categorical_space_signature(
        {
            "batch_size": [256, 128, 64],
            "hidden_size": [96, 64],
        }
    )

    assert sig_a == sig_b
    assert sig_a  # non-empty for non-empty categorical space


def test_categorical_space_signature_changes_when_a_choice_drops() -> None:
    """Shrinking `hidden_size` from [64,96,128] to [64,96] must change the
    signature so a fresh study name is chosen.
    """
    wide = _categorical_space_signature({"hidden_size": [64, 96, 128]})
    narrow = _categorical_space_signature({"hidden_size": [64, 96]})
    assert wide != narrow


def test_study_detects_incompatible_categorical_values(sqlite_storage: str) -> None:
    """A persisted trial with `hidden_size=128` must flag as incompatible
    when the current search space is `[64, 96]`.
    """
    _seed_study_with_trial(sqlite_storage, "cluster-v2/Utilities", hidden_size=128)
    study = optuna.load_study(study_name="cluster-v2/Utilities", storage=sqlite_storage)

    incompatible, diagnostic = _study_has_incompatible_categorical_values(
        study, {"hidden_size": [64, 96]}
    )

    assert incompatible is True
    assert "hidden_size" in (diagnostic or "")
    assert "128" in (diagnostic or "")


def test_study_is_compatible_when_all_values_still_in_space(
    sqlite_storage: str,
) -> None:
    _seed_study_with_trial(sqlite_storage, "cluster-v2/Technology_0", hidden_size=96)
    study = optuna.load_study(study_name="cluster-v2/Technology_0", storage=sqlite_storage)

    incompatible, diagnostic = _study_has_incompatible_categorical_values(
        study, {"hidden_size": [64, 96]}
    )

    assert incompatible is False
    assert diagnostic is None


def test_resolve_study_name_returns_base_when_no_prior_study(
    sqlite_storage: str,
) -> None:
    """First run for a cluster: no persisted study, base name is used."""
    name = _resolve_cluster_study_name(
        "BrandNewCluster",
        {"search_space": {"hidden_size": [64, 96]}},
        storage=sqlite_storage,
    )
    assert name == "cluster-v2/BrandNewCluster"


def test_resolve_study_name_bumps_when_categorical_shrinks(
    sqlite_storage: str,
) -> None:
    """After BEC-42 narrows `hidden_size` for a cluster, the resolver must
    return a new study name so `create_study(load_if_exists=True)` builds a
    fresh history instead of crashing on the stale `128` choice.
    """
    _seed_study_with_trial(sqlite_storage, "cluster-v2/Utilities", hidden_size=128)

    narrow_cfg = {"search_space": {"hidden_size": [64, 96]}}
    bumped = _resolve_cluster_study_name("Utilities", narrow_cfg, storage=sqlite_storage)

    assert bumped != "cluster-v2/Utilities"
    assert bumped.startswith("cluster-v2/Utilities#")

    # Sanity: creating a study under the bumped name + suggesting the
    # narrowed categorical must NOT raise (this is exactly the code path
    # that previously crashed in production).
    study = optuna.create_study(
        study_name=bumped,
        storage=sqlite_storage,
        direction="maximize",
        load_if_exists=True,
    )

    def objective(trial: optuna.Trial) -> float:
        return float(trial.suggest_categorical("hidden_size", [64, 96]))

    study.optimize(objective, n_trials=1)


def test_resolve_study_name_keeps_base_when_space_is_still_compatible(
    sqlite_storage: str,
) -> None:
    """If the persisted study's categorical values are still valid under
    the current search space, we must keep warm-starting from the same
    study rather than forking a new one.
    """
    _seed_study_with_trial(sqlite_storage, "cluster-v2/Technology_0", hidden_size=96)

    cfg = {"search_space": {"hidden_size": [64, 96, 128]}}
    resolved = _resolve_cluster_study_name("Technology_0", cfg, storage=sqlite_storage)

    assert resolved == "cluster-v2/Technology_0"


def test_resolve_study_name_without_storage_returns_base() -> None:
    """In-memory mode has no persistence, so the resolver must return the
    base name unconditionally (no study to inspect).
    """
    name = _resolve_cluster_study_name(
        "SomeCluster",
        {"search_space": {"hidden_size": [64, 96]}},
        storage=None,
    )
    assert name == "cluster-v2/SomeCluster"
