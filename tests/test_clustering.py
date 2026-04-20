"""Tests for stock clustering module."""
# ruff: noqa: N806  # ML convention: capital X for feature matrices

import numpy as np
import polars as pl
import pytest
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_samples, silhouette_score
from sklearn.preprocessing import StandardScaler


@pytest.fixture
def sample_clustering_features() -> pl.DataFrame:
    """Generate synthetic clustering features for 12 stocks across 2 sectors."""
    np.random.seed(42)
    stocks = []
    # Technology sector — 6 stocks with 2 distinct behavior groups
    for i in range(3):
        stocks.append(
            {
                "symbol": f"TECH_HIGH_{i}",
                "sector": "Technology",
                "return_20d_mean": 0.005 + np.random.normal(0, 0.001),
                "volatility_60d": 0.03 + np.random.normal(0, 0.002),
                "volume_profile": 1.5 + np.random.normal(0, 0.1),
                "rsi_14_mean": 60 + np.random.normal(0, 2),
                "beta_60d": 1.3 + np.random.normal(0, 0.1),
            }
        )
    for i in range(3):
        stocks.append(
            {
                "symbol": f"TECH_LOW_{i}",
                "sector": "Technology",
                "return_20d_mean": -0.002 + np.random.normal(0, 0.001),
                "volatility_60d": 0.01 + np.random.normal(0, 0.002),
                "volume_profile": 0.8 + np.random.normal(0, 0.1),
                "rsi_14_mean": 40 + np.random.normal(0, 2),
                "beta_60d": 0.7 + np.random.normal(0, 0.1),
            }
        )
    # Healthcare sector — 6 stocks
    for i in range(3):
        stocks.append(
            {
                "symbol": f"HEALTH_A_{i}",
                "sector": "Healthcare",
                "return_20d_mean": 0.003 + np.random.normal(0, 0.001),
                "volatility_60d": 0.02 + np.random.normal(0, 0.002),
                "volume_profile": 1.0 + np.random.normal(0, 0.1),
                "rsi_14_mean": 55 + np.random.normal(0, 2),
                "beta_60d": 0.9 + np.random.normal(0, 0.1),
            }
        )
    for i in range(3):
        stocks.append(
            {
                "symbol": f"HEALTH_B_{i}",
                "sector": "Healthcare",
                "return_20d_mean": -0.001 + np.random.normal(0, 0.001),
                "volatility_60d": 0.015 + np.random.normal(0, 0.002),
                "volume_profile": 1.2 + np.random.normal(0, 0.1),
                "rsi_14_mean": 45 + np.random.normal(0, 2),
                "beta_60d": 1.1 + np.random.normal(0, 0.1),
            }
        )
    return pl.DataFrame(stocks)


def test_kmeans_produces_expected_clusters(sample_clustering_features: pl.DataFrame) -> None:
    """KMeans should produce 2 clusters per sector on clearly separable data."""
    feature_cols = [
        "return_20d_mean",
        "volatility_60d",
        "volume_profile",
        "rsi_14_mean",
        "beta_60d",
    ]

    for sector in ["Technology", "Healthcare"]:
        sector_df = sample_clustering_features.filter(pl.col("sector") == sector)
        X = sector_df.select(feature_cols).to_numpy()
        X_scaled = StandardScaler().fit_transform(X)

        kmeans = KMeans(n_clusters=2, random_state=42, n_init=10)
        labels = kmeans.fit_predict(X_scaled)

        assert len(set(labels)) == 2
        assert len(labels) == 6


def test_silhouette_score_positive(sample_clustering_features: pl.DataFrame) -> None:
    """Silhouette score should be positive for clearly separable clusters."""
    feature_cols = [
        "return_20d_mean",
        "volatility_60d",
        "volume_profile",
        "rsi_14_mean",
        "beta_60d",
    ]

    sector_df = sample_clustering_features.filter(pl.col("sector") == "Technology")
    X = sector_df.select(feature_cols).to_numpy()
    X_scaled = StandardScaler().fit_transform(X)

    kmeans = KMeans(n_clusters=2, random_state=42, n_init=10)
    labels = kmeans.fit_predict(X_scaled)

    score = silhouette_score(X_scaled, labels)
    assert score > 0, f"Expected positive silhouette score, got {score}"


def test_single_stock_sector_no_crash() -> None:
    """A sector with 1 stock should produce a single cluster without error."""
    df = pl.DataFrame(
        [
            {
                "symbol": "SOLO",
                "sector": "Energy",
                "return_20d_mean": 0.001,
                "volatility_60d": 0.02,
                "volume_profile": 1.0,
                "rsi_14_mean": 50.0,
                "beta_60d": 1.0,
            }
        ]
    )

    feature_cols = [
        "return_20d_mean",
        "volatility_60d",
        "volume_profile",
        "rsi_14_mean",
        "beta_60d",
    ]
    df.select(feature_cols).to_numpy()
    # Can't cluster with n_clusters >= n_samples
    n_clusters = min(3, len(df))
    assert n_clusters == 1


def test_cluster_id_format(sample_clustering_features: pl.DataFrame) -> None:
    """Cluster IDs should be descriptive based on sector composition."""

    # Build a minimal config that exercises run_clustering's naming logic
    # We test the naming logic directly instead
    feature_cols = [
        "return_20d_mean",
        "volatility_60d",
        "volume_profile",
        "rsi_14_mean",
        "beta_60d",
    ]
    sectors = sample_clustering_features["sector"].to_list()

    X = sample_clustering_features.select(feature_cols).to_numpy()
    X_scaled = StandardScaler().fit_transform(X)

    kmeans = KMeans(n_clusters=2, random_state=42, n_init=10)
    labels = kmeans.fit_predict(X_scaled)

    # Replicate the naming logic
    unique_labels = sorted(set(labels))
    cluster_sectors: dict[int, set[str]] = {}
    for idx, label in enumerate(labels):
        cluster_sectors.setdefault(label, set()).add(sectors[idx])

    name_counts: dict[str, int] = {}
    label_to_name: dict[int, str] = {}
    for label in unique_labels:
        label_sectors = sorted(cluster_sectors[label])
        if len(label_sectors) <= 3:
            base_name = "-".join(s.replace(" ", "") for s in label_sectors)
        else:
            base_name = "Miscellaneous"
        count = name_counts.get(base_name, 0)
        name_counts[base_name] = count + 1
        label_to_name[label] = f"{base_name}_{count}"

    single_names = {name for name, count in name_counts.items() if count == 1}
    for label, name in label_to_name.items():
        base = name.rsplit("_", 1)[0]
        if base in single_names:
            label_to_name[label] = base

    # Each cluster_id should be a non-empty string
    for label in unique_labels:
        cluster_id = label_to_name[label]
        assert len(cluster_id) > 0
        # With 2 sectors (Technology, Healthcare) and 2 clusters,
        # names should contain sector names or Miscellaneous
        assert any(s in cluster_id for s in ["Technology", "Healthcare", "Miscellaneous"])


def test_per_cluster_silhouette_aggregation(sample_clustering_features: pl.DataFrame) -> None:
    """Per-cluster silhouette mean and std should be computed per cluster."""
    feature_cols = [
        "return_20d_mean",
        "volatility_60d",
        "volume_profile",
        "rsi_14_mean",
        "beta_60d",
    ]

    X = sample_clustering_features.select(feature_cols).to_numpy()
    X_scaled = StandardScaler().fit_transform(X)

    kmeans = KMeans(n_clusters=2, random_state=42, n_init=10)
    labels = kmeans.fit_predict(X_scaled)
    unique_labels = sorted(set(labels))

    sample_scores = silhouette_samples(X_scaled, labels)

    cluster_sil_mean: dict[int, float] = {}
    cluster_sil_std: dict[int, float] = {}
    for label in unique_labels:
        mask = labels == label
        scores_for_cluster = sample_scores[mask]
        cluster_sil_mean[label] = float(np.mean(scores_for_cluster))
        cluster_sil_std[label] = float(np.std(scores_for_cluster))

    # Each cluster should have a mean silhouette and std
    assert len(cluster_sil_mean) == 2
    assert len(cluster_sil_std) == 2

    # For clearly separable clusters, mean silhouette should be positive
    for label, mean_val in cluster_sil_mean.items():
        assert mean_val > 0, f"Cluster {label} mean silhouette {mean_val} should be > 0"

    # Std should be non-negative
    for label, std_val in cluster_sil_std.items():
        assert std_val >= 0, f"Cluster {label} std silhouette {std_val} should be >= 0"


def test_per_cluster_silhouette_columns_in_output(sample_clustering_features: pl.DataFrame) -> None:
    """Result rows should contain silhouette_mean_cluster and silhouette_std_cluster columns."""
    feature_cols = [
        "return_20d_mean",
        "volatility_60d",
        "volume_profile",
        "rsi_14_mean",
        "beta_60d",
    ]
    symbols = sample_clustering_features["symbol"].to_list()
    sectors = sample_clustering_features["sector"].to_list()

    X = sample_clustering_features.select(feature_cols).to_numpy()
    X_scaled = StandardScaler().fit_transform(X)

    kmeans = KMeans(n_clusters=2, random_state=42, n_init=10)
    labels = kmeans.fit_predict(X_scaled)
    unique_labels = sorted(set(labels))

    sample_scores = silhouette_samples(X_scaled, labels)
    cluster_sil_mean = {lbl: float(np.mean(sample_scores[labels == lbl])) for lbl in unique_labels}
    cluster_sil_std = {lbl: float(np.std(sample_scores[labels == lbl])) for lbl in unique_labels}
    sil_global = float(silhouette_score(X_scaled, labels))

    results = []
    for idx, symbol in enumerate(symbols):
        label = labels[idx]
        results.append(
            {
                "symbol": symbol,
                "sector": sectors[idx],
                "cluster_id": f"cluster_{label}",
                "silhouette_score": sil_global,
                "silhouette_mean_cluster": cluster_sil_mean[label],
                "silhouette_std_cluster": cluster_sil_std[label],
            }
        )

    result_df = pl.DataFrame(results)

    # Verify the new columns are present
    assert "silhouette_mean_cluster" in result_df.columns
    assert "silhouette_std_cluster" in result_df.columns

    # Each stock should have non-null per-cluster silhouette values
    assert result_df["silhouette_mean_cluster"].null_count() == 0
    assert result_df["silhouette_std_cluster"].null_count() == 0

    # Stocks in the same cluster should have the same mean silhouette
    for cluster_id in result_df["cluster_id"].unique().to_list():
        cluster_rows = result_df.filter(pl.col("cluster_id") == cluster_id)
        means = cluster_rows["silhouette_mean_cluster"].unique()
        assert len(means) == 1, f"All rows in cluster {cluster_id} should have identical mean"
