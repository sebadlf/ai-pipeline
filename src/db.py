"""Database connection and table setup."""

from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    Float,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    create_engine,
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


def get_engine() -> Engine:
    """Create SQLAlchemy engine."""
    return create_engine(get_db_url())


def init_db(engine: Engine) -> None:
    """Create tables and enable TimescaleDB extension."""
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE"))
        conn.commit()
    metadata.create_all(engine)
