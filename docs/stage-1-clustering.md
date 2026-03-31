# Stage 1: Stock Clustering

**File**: `src/features/clustering.py`
**Makefile target**: `make cluster`
**Command**: `uv run python -m src.features.clustering`

## Purpose

Group stocks into behaviorally similar clusters within each GICS sector. Each cluster then gets its own LSTM model in Stage 2, allowing models to specialize for stocks with similar return profiles, volatility patterns, fundamental characteristics, and macro sensitivities.

## Why Per-Sector Then Per-Cluster

Stocks in different sectors (e.g., Technology vs Utilities) have fundamentally different dynamics. Clustering across sectors would produce noisy groupings. Instead, the pipeline first groups by GICS sector (from `stock_sectors` table), then runs KMeans within each sector to find sub-groups.

## Clustering Features (19)

Features are computed from the training period only (before `train_end`) to avoid data leakage.

### Behavioral (7)

| Feature | Computation | Purpose |
|---|---|---|
| `return_20d_mean` | Mean of 20-day rolling returns | Average momentum |
| `volatility_60d` | Std of daily returns over 60 days | Risk profile |
| `volume_profile` | Mean of relative_volume (volume / SMA_20) | Liquidity characteristics |
| `rsi_14_mean` | Mean of RSI(14) | Overbought/oversold tendency |
| `beta_60d` | Covariance(stock, SPY) / Var(SPY) over 60 days | Market sensitivity |
| `momentum_60d` | Cumulative 60-day return | Medium-term trend strength |
| `drawdown_max` | Maximum drawdown during training period | Tail risk profile |

### Macro Sensitivity (2)

| Feature | Computation | Purpose |
|---|---|---|
| `vix_beta` | Regression of stock daily returns on VIX daily returns (trailing 252d) | Volatility sensitivity |
| `yield_sensitivity` | Regression of stock daily returns on 10Y-2Y spread daily changes (trailing 252d) | Interest rate sensitivity |

### Sector-Relative (1)

| Feature | Computation | Purpose |
|---|---|---|
| `relative_to_sector_avg` | Stock's avg daily return minus sector's avg daily return | Outperformance within sector |

### Fundamentals (9)

Most recent quarterly values before `train_end`, from `key_metrics_quarterly` and `financial_ratios_quarterly`:

| Feature | Source | Purpose |
|---|---|---|
| `km_returnOnEquity` | Key Metrics | Profitability |
| `km_earningsYield` | Key Metrics | Valuation (inverse P/E) |
| `km_freeCashFlowYield` | Key Metrics | Cash generation |
| `km_evToEBITDA` | Key Metrics | Enterprise valuation |
| `fr_grossProfitMargin` | Financial Ratios | Operating efficiency |
| `fr_netProfitMargin` | Financial Ratios | Bottom-line profitability |
| `fr_debtToEquityRatio` | Financial Ratios | Leverage |
| `fr_priceToEarningsRatio` | Financial Ratios | Valuation |
| `fr_priceToBookRatio` | Financial Ratios | Asset valuation |
| `fr_dividendYield` | Financial Ratios | Income profile |

## Clustering Algorithm

### Pipeline per Sector

```
Stocks in sector
    │
    ▼
Compute 19 features per stock
    │
    ▼
Handle NaN (fill with column medians)
    │
    ▼
StandardScaler (zero mean, unit variance)
    │
    ▼
PCA (retain 95% of explained variance)
    │
    ▼
Silhouette search: K = 2..max_clusters_per_sector
    │
    ▼
KMeans with optimal K
    │
    ▼
Merge clusters smaller than min_cluster_size
    │
    ▼
Assign cluster_id = "{Sector}_{k}"
```

### PCA Dimensionality Reduction

With 19 features, many are correlated (e.g., ROE with net profit margin, P/E with earnings yield). PCA reduces to the components explaining `pca_variance_ratio` (default 0.95 = 95%) of variance before clustering. This prevents correlated features from dominating the Euclidean distance in KMeans.

### Automatic K Selection

Instead of a fixed number of clusters, the pipeline tests K from 2 to `max_clusters_per_sector` (default 6) and selects the K with the highest silhouette score. If the best K produces any cluster smaller than `min_cluster_size` (default 3), the next-best K is tried.

### Small Cluster Merging

After KMeans, clusters with fewer than `min_cluster_size` stocks are merged into the nearest larger cluster based on centroid distance.

## Configuration

```yaml
clustering:
  method: kmeans
  max_clusters_per_sector: 6
  pca_variance_ratio: 0.95
  min_cluster_size: 3
  features_for_clustering:
    - return_20d_mean
    - volatility_60d
    - volume_profile
    # ... (19 features listed in default.yaml)
  output_parquet: data/clusters.parquet
  cluster_thresholds: {}   # per-cluster BUY/SELL threshold overrides
```

### Per-Cluster Threshold Overrides

The `cluster_thresholds` map allows setting different BUY/SELL thresholds per cluster:

```yaml
cluster_thresholds:
  Technology_0:
    buy_threshold: 0.07
    sell_threshold: 0.04
```

Clusters not listed use the global defaults from `target.buy_threshold` and `target.sell_threshold`.

## Output

### `data/clusters.parquet`
| Column | Type | Description |
|---|---|---|
| symbol | str | Stock ticker |
| cluster_id | str | e.g. "Technology_0", "Healthcare_1" |
| sector | str | GICS sector name |

### `cluster_assignments` table (PostgreSQL)
Same columns, upserted with `ON CONFLICT (symbol) DO UPDATE`.

## MLflow Logging

- **Experiment**: `clustering`
- **Run name**: `cluster-assignment`
- **Parameters**: `n_sectors`, `total_symbols`, `total_clusters`, per-sector K and silhouette scores
- **Metrics**: `avg_silhouette`, per-sector `{sector}_k`, `{sector}_silhouette`, `{sector}_pca_components`
- **Artifact**: `data/clusters.parquet`
