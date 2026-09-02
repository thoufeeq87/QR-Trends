from datetime import datetime
from pathlib import Path

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


class Base(DeclarativeBase):
    pass


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str | None] = mapped_column(Text)
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    priority: Mapped[str] = mapped_column(String, nullable=False, default="normal")
    domain: Mapped[str] = mapped_column(String, nullable=False, default="qa")
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("type IN ('rss','reddit_json','hn_api','youtube_atom','manual')", name="sources_type_check"),
        CheckConstraint("domain IN ('qa','agents')", name="sources_domain_check"),
    )


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), nullable=False)
    external_url: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    short_summary: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str] = mapped_column(String, nullable=False, default="qa")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("label", "domain", name="topics_label_domain_key"),
        CheckConstraint("domain IN ('qa','agents')", name="topics_domain_check"),
    )


class ItemTopic(Base):
    __tablename__ = "item_topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("item_id", "topic_id", name="item_topics_item_id_topic_id_key"),)


class TopicTrend(Base):
    __tablename__ = "topic_trends"

    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True)
    current_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prior_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    trend_label: Mapped[str] = mapped_column(String, nullable=False)
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("trend_label IN ('new','trending','stable','declining')", name="topic_trends_label_check"),
    )


def ensure_schema() -> None:
    """Apply every migrations/*.sql file, in order, on every startup. Each one is
    written idempotently (CREATE TABLE IF NOT EXISTS, ADD COLUMN IF NOT EXISTS, ...),
    so this is safe to re-run unconditionally — it's the project's whole migration
    story: no separate tracking table, just idempotent SQL files applied in name
    order every boot."""
    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    with engine.begin() as conn:
        for path in migration_files:
            conn.execute(text(path.read_text()))
