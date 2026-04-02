"""Database connection and table setup."""

from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    create_engine,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine

from src.config import get_db_url

metadata = MetaData()

ohlcv_daily = Table(
    "ohlcv_daily",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("symbol", String(10), nullable=False),
    Column("date", Date, nullable=False),
    Column("open", Float, nullable=False),
    Column("high", Float, nullable=False),
    Column("low", Float, nullable=False),
    Column("close", Float, nullable=False),
    Column("adj_close", Float),
    Column("volume", BigInteger, nullable=False),
    Column("change_percent", Float),
    UniqueConstraint("symbol", "date", name="uq_ohlcv_symbol_date"),
)

treasury_rates = Table(
    "treasury_rates",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("date", Date, nullable=False, unique=True),
    Column("month1", Float),
    Column("month2", Float),
    Column("month3", Float),
    Column("month6", Float),
    Column("year1", Float),
    Column("year2", Float),
    Column("year3", Float),
    Column("year5", Float),
    Column("year7", Float),
    Column("year10", Float),
    Column("year20", Float),
    Column("year30", Float),
)

key_metrics_quarterly = Table(
    "key_metrics_quarterly",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("symbol", String(10), nullable=False),
    Column("date", Date, nullable=False),
    Column("fiscal_year", String(4)),
    Column("period", String(4)),
    Column("data", JSONB),
    UniqueConstraint("symbol", "date", "period", name="uq_km_symbol_date_period"),
)

financial_ratios_quarterly = Table(
    "financial_ratios_quarterly",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("symbol", String(10), nullable=False),
    Column("date", Date, nullable=False),
    Column("fiscal_year", String(4)),
    Column("period", String(4)),
    Column("data", JSONB),
    UniqueConstraint("symbol", "date", "period", name="uq_fr_symbol_date_period"),
)

sector_performance_daily = Table(
    "sector_performance_daily",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("date", Date, nullable=False),
    Column("sector", String(100), nullable=False),
    Column("exchange", String(20), nullable=False),
    Column("average_change", Float),
    UniqueConstraint("date", "sector", "exchange", name="uq_sp_date_sector_exchange"),
)

vix_daily = Table(
    "vix_daily",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("date", Date, nullable=False, unique=True),
    Column("open", Float),
    Column("high", Float),
    Column("low", Float),
    Column("close", Float),
    Column("change_percent", Float),
)

# --- New tables for 5-stage pipeline ---

stock_sectors = Table(
    "stock_sectors",
    metadata,
    Column("symbol", String(10), primary_key=True),
    Column("sector", String(100), nullable=False),
    Column("sub_industry", String(200)),
    Column("updated_at", DateTime, server_default=func.now()),
)

cluster_assignments = Table(
    "cluster_assignments",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("run_date", Date, nullable=False),
    Column("symbol", String(10), nullable=False),
    Column("sector", String(100), nullable=False),
    Column("cluster_id", String(50), nullable=False),
    Column("silhouette_score", Float),
    UniqueConstraint("run_date", "symbol", name="uq_cluster_run_symbol"),
)

predictions = Table(
    "predictions",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("run_date", Date, nullable=False),
    Column("symbol", String(10), nullable=False),
    Column("cluster_id", String(50), nullable=False),
    Column("prob_up", Float, nullable=False),
    Column("model_run_id", String(64)),
    UniqueConstraint("run_date", "symbol", name="uq_pred_run_symbol"),
)

portfolio_allocations = Table(
    "portfolio_allocations",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("run_date", Date, nullable=False),
    Column("profile", String(20), nullable=False),
    Column("symbol", String(10), nullable=False),
    Column("weight", Float, nullable=False),
    Column("prob_up", Float),
    Column("cluster_id", String(50), nullable=False),
    UniqueConstraint("run_date", "profile", "symbol", name="uq_alloc_run_profile_symbol"),
)

backtest_results = Table(
    "backtest_results",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("run_date", Date, nullable=False),
    Column("profile", String(20), nullable=False),
    Column("regime", String(20), nullable=False),
    Column("total_return", Float),
    Column("annual_return", Float),
    Column("sharpe_ratio", Float),
    Column("sortino_ratio", Float),
    Column("calmar_ratio", Float),
    Column("omega_ratio", Float),
    Column("info_ratio", Float),
    Column("max_drawdown", Float),
    Column("win_rate", Float),
    Column("num_trades", Integer),
    UniqueConstraint("run_date", "profile", "regime", name="uq_bt_run_profile_regime"),
)


_engine: Engine | None = None


def get_engine() -> Engine:
    """Create SQLAlchemy engine (singleton) and run migrations on first call."""
    global _engine
    if _engine is None:
        _engine = create_engine(get_db_url())
        init_db(_engine)
    return _engine


def init_db(engine: Engine) -> None:
    """Create tables, enable TimescaleDB, and migrate schemas."""
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE"))
        conn.commit()
    metadata.create_all(engine)

    _migrate_treasury_columns(engine)
    _migrate_predictions_to_prob_up(engine)


def _migrate_treasury_columns(engine: Engine) -> None:
    """Add new treasury tenor columns to existing table if missing."""
    new_cols = [
        "month1", "month2", "month3", "month6",
        "year1", "year3", "year5", "year7", "year20",
    ]
    with engine.begin() as conn:
        for col in new_cols:
            conn.execute(text(
                f"ALTER TABLE treasury_rates ADD COLUMN IF NOT EXISTS {col} DOUBLE PRECISION"
            ))


def _migrate_predictions_to_prob_up(engine: Engine) -> None:
    """Migrate predictions and portfolio_allocations tables to prob_up schema."""
    with engine.begin() as conn:
        # Predictions: add prob_up, backfill from prob_buy, drop old columns
        conn.execute(text(
            "ALTER TABLE predictions ADD COLUMN IF NOT EXISTS prob_up DOUBLE PRECISION"
        ))
        # Backfill from prob_buy if it still exists (idempotent)
        has_prob_buy = conn.execute(text("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'predictions' AND column_name = 'prob_buy'
        """)).fetchone()
        if has_prob_buy:
            conn.execute(text("""
                UPDATE predictions SET prob_up = prob_buy
                WHERE prob_up IS NULL AND prob_buy IS NOT NULL
            """))
        for col in ["prediction", "confidence", "prob_buy", "prob_sell", "prob_hold"]:
            conn.execute(text(
                f"ALTER TABLE predictions DROP COLUMN IF EXISTS {col}"
            ))

        # Portfolio allocations: add prob_up, drop signal
        conn.execute(text(
            "ALTER TABLE portfolio_allocations ADD COLUMN IF NOT EXISTS prob_up DOUBLE PRECISION"
        ))
        conn.execute(text(
            "ALTER TABLE portfolio_allocations DROP COLUMN IF EXISTS signal"
        ))
