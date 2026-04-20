"""Tests for src.config helpers (per-cluster Optuna overrides)."""

from __future__ import annotations

import copy

import pytest

from src.config import (
    effective_config_for_cluster,
    get_cluster_optuna_config,
)


@pytest.fixture
def base_config() -> dict:
    """Minimal config with the Optuna sub-section exercised by overrides."""
    return {
        "training": {
            "optuna": {
                "n_trials": {"dev": 5, "prod": 15},
                "max_overfit_gap": 0.30,
                "cv_folds": 3,
                "search_space": {
                    "hidden_size": [64, 96, 128],
                    "dropout": {"low": 0.2, "high": 0.65},
                    "learning_rate": {"low": 1e-4, "high": 1e-2, "log": True},
                },
                "fixed_params": {
                    "activation": "gelu",
                    "feature_mask_rate": 0.10,
                    "bidirectional": False,
                },
                "per_cluster_overrides": {
                    "Utilities": {
                        "max_overfit_gap": 0.15,
                        "search_space": {
                            "hidden_size": [64, 96],
                            "dropout": {"high": 0.5},
                        },
                        "fixed_params": {"feature_mask_rate": 0.15},
                    },
                    "FinancialServices": {
                        "max_overfit_gap": 0.15,
                    },
                },
            },
        },
    }


def test_get_cluster_optuna_config_no_override_returns_base(base_config):
    """Clusters without overrides get a deep copy of the base optuna config."""
    result = get_cluster_optuna_config(base_config, "Technology")
    expected = base_config["training"]["optuna"]

    # Values match
    assert result["max_overfit_gap"] == expected["max_overfit_gap"]
    assert result["search_space"]["hidden_size"] == expected["search_space"]["hidden_size"]
    assert (
        result["fixed_params"]["feature_mask_rate"] == expected["fixed_params"]["feature_mask_rate"]
    )

    # Mutations on result don't leak into the base
    result["max_overfit_gap"] = 0.99
    result["search_space"]["hidden_size"].append(256)
    assert base_config["training"]["optuna"]["max_overfit_gap"] == 0.30
    assert base_config["training"]["optuna"]["search_space"]["hidden_size"] == [64, 96, 128]


def test_get_cluster_optuna_config_scalar_override(base_config):
    """Scalar overrides (e.g., max_overfit_gap) replace base values."""
    result = get_cluster_optuna_config(base_config, "FinancialServices")
    assert result["max_overfit_gap"] == 0.15
    # Unaffected keys preserved
    assert result["cv_folds"] == 3
    assert result["search_space"]["hidden_size"] == [64, 96, 128]
    assert result["fixed_params"]["feature_mask_rate"] == 0.10


def test_get_cluster_optuna_config_search_space_and_fixed_merge(base_config):
    """Search-space and fixed_params overrides merge correctly."""
    result = get_cluster_optuna_config(base_config, "Utilities")

    # Scalar override applied
    assert result["max_overfit_gap"] == 0.15

    # List spec wholesale-replaced
    assert result["search_space"]["hidden_size"] == [64, 96]

    # Dict spec field-merged: `high` overridden, `low` preserved
    dropout = result["search_space"]["dropout"]
    assert dropout == {"low": 0.2, "high": 0.5}

    # Non-overridden search-space entry preserved
    lr = result["search_space"]["learning_rate"]
    assert lr == {"low": 1e-4, "high": 1e-2, "log": True}

    # fixed_params: overridden key replaced, others preserved
    fp = result["fixed_params"]
    assert fp["feature_mask_rate"] == 0.15
    assert fp["activation"] == "gelu"
    assert fp["bidirectional"] is False


def test_get_cluster_optuna_config_does_not_mutate_input(base_config):
    """The helper must never mutate its input (defensive copy)."""
    snapshot = copy.deepcopy(base_config)
    get_cluster_optuna_config(base_config, "Utilities")
    assert base_config == snapshot


def test_effective_config_for_cluster_replaces_only_optuna(base_config):
    """effective_config_for_cluster swaps optuna section without touching others."""
    base_config["clustering"] = {"method": "kmeans"}
    base_config["training"]["batch_size"] = {"dev": 256}

    effective = effective_config_for_cluster(base_config, "Utilities")

    # Optuna section reflects overrides
    assert effective["training"]["optuna"]["max_overfit_gap"] == 0.15
    assert effective["training"]["optuna"]["search_space"]["hidden_size"] == [64, 96]

    # Untouched siblings preserved by reference or value
    assert effective["training"]["batch_size"] == {"dev": 256}
    assert effective["clustering"] == {"method": "kmeans"}

    # Base config untouched
    assert base_config["training"]["optuna"]["max_overfit_gap"] == 0.30


def test_effective_config_for_cluster_no_override(base_config):
    """Clusters without overrides still get a shallow-copied config."""
    effective = effective_config_for_cluster(base_config, "Technology")
    assert effective["training"]["optuna"]["max_overfit_gap"] == 0.30
    # Shallow-copied: top-level dict is a new object
    assert effective is not base_config
    assert effective["training"] is not base_config["training"]
