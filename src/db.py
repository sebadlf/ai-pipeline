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
    Column("year2", Float),
    Column("year10", Float),
    Column("year30", Float),
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
    Column("prediction", String(4), nullable=False),
    Column("confidence", Float, nullable=False),
    Column("prob_buy", Float, nullable=False),
    Column("prob_sell", Float, nullable=False),
    Column("prob_hold", Float, nullable=False),
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
    Column("signal", String(4), nullable=False),
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


def get_engine() -> Engine:
    """Create SQLAlchemy engine."""
    return create_engine(get_db_url())


def init_db(engine: Engine) -> None:
    """Create tables and enable TimescaleDB extension."""
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE"))
        conn.commit()
    metadata.create_all(engine)
