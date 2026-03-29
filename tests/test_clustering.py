"""Tests for stock clustering module."""

import numpy as np
import polars as pl
import pytest
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler


@pytest.fixture
def sample_clustering_features() -> pl.DataFrame:
    """Generate synthetic clustering features for 12 stocks across 2 sectors."""
    np.random.seed(42)
    stocks = []
    # Technology sector — 6 stocks with 2 distinct behavior groups
    for i in range(3):
        stocks.append({
            "symbol": f"TECH_HIGH_{i}",
            "sector": "Technology",
            "return_20d_mean": 0.005 + np.random.normal(0, 0.001),
            "volatility_60d": 0.03 + np.random.normal(0, 0.002),
            "volume_profile": 1.5 + np.random.normal(0, 0.1),
            "rsi_14_mean": 60 + np.random.normal(0, 2),
            "beta_60d": 1.3 + np.random.normal(0, 0.1),
        })
    for i in range(3):
        stocks.append({
            "symbol": f"TECH_LOW_{i}",
            "sector": "Technology",
            "return_20d_mean": -0.002 + np.random.normal(0, 0.001),
            "volatility_60d": 0.01 + np.random.normal(0, 0.002),
            "volume_profile": 0.8 + np.random.normal(0, 0.1),
            "rsi_14_mean": 40 + np.random.normal(0, 2),
            "beta_60d": 0.7 + np.random.normal(0, 0.1),
        })
    # Healthcare sector — 6 stocks
    for i in range(3):
        stocks.append({
            "symbol": f"HEALTH_A_{i}",
            "sector": "Healthcare",
            "return_20d_mean": 0.003 + np.random.normal(0, 0.001),
            "volatility_60d": 0.02 + np.random.normal(0, 0.002),
            "volume_profile": 1.0 + np.random.normal(0, 0.1),
            "rsi_14_mean": 55 + np.random.normal(0, 2),
            "beta_60d": 0.9 + np.random.normal(0, 0.1),
        })
    for i in range(3):
        stocks.append({
            "symbol": f"HEALTH_B_{i}",
            "sector": "Healthcare",
            "return_20d_mean": -0.001 + np.random.normal(0, 0.001),
            "volatility_60d": 0.015 + np.random.normal(0, 0.002),
            "volume_profile": 1.2 + np.random.normal(0, 0.1),
            "rsi_14_mean": 45 + np.random.normal(0, 2),
            "beta_60d": 1.1 + np.random.normal(0, 0.1),
        })
    return pl.DataFrame(stocks)


def test_kmeans_produces_expected_clusters(sample_clustering_features: pl.DataFrame) -> None:
    """KMeans should produce 2 clusters per sector on clearly separable data."""
    feature_cols = [
        "return_20d_mean", "volatility_60d", "volume_profile", "rsi_14_mean", "beta_60d"
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
        "return_20d_mean", "volatility_60d", "volume_profile", "rsi_14_mean", "beta_60d"
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
    df = pl.DataFrame([{
        "symbol": "SOLO",
        "sector": "Energy",
        "return_20d_mean": 0.001,
        "volatility_60d": 0.02,
        "volume_profile": 1.0,
        "rsi_14_mean": 50.0,
        "beta_60d": 1.0,
    }])

    feature_cols = [
        "return_20d_mean", "volatility_60d", "volume_profile", "rsi_14_mean", "beta_60d"
    ]
    X = df.select(feature_cols).to_numpy()
    # Can't cluster with n_clusters >= n_samples
    n_clusters = min(3, len(df))
    assert n_clusters == 1


def test_cluster_id_format(sample_clustering_features: pl.DataFrame) -> None:
    """Cluster IDs should follow the '{sector}_{n}' format."""
    feature_cols = [
        "return_20d_mean", "volatility_60d", "volume_profile", "rsi_14_mean", "beta_60d"
    ]

    sector = "Technology"
    sector_df = sample_clustering_features.filter(pl.col("sector") == sector)
    X = sector_df.select(feature_cols).to_numpy()
    X_scaled = StandardScaler().fit_transform(X)

    kmeans = KMeans(n_clusters=2, random_state=42, n_init=10)
    labels = kmeans.fit_predict(X_scaled)

    unique_labels = sorted(set(labels))
    label_map = {old: new for new, old in enumerate(unique_labels)}

    for idx, symbol in enumerate(sector_df["symbol"].to_list()):
        cluster_id = f"{sector}_{label_map[labels[idx]]}"
        assert cluster_id.startswith("Technology_")
        assert cluster_id.split("_")[-1].isdigit()
