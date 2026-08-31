from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import Item, ItemTopic, Source, Topic, TopicTrend

SECTION_TREND_LABELS = {
    "new": ["new"],
    "relevant": ["stable", "trending"],
    "fading": ["declining"],
}

SPARKLINE_WEEKS = 8
RECENT_ITEMS_LIMIT = 3


def get_topic_cards(db: Session, section: str) -> list[dict]:
    trend_labels = SECTION_TREND_LABELS[section]

    trends = (
        db.query(TopicTrend, Topic)
        .join(Topic, Topic.id == TopicTrend.topic_id)
        .filter(TopicTrend.trend_label.in_(trend_labels))
        .order_by(TopicTrend.current_count.desc())
        .all()
    )

    return [_build_card(db, trend, topic) for trend, topic in trends]


def get_topic_card(db: Session, topic_id: int) -> dict | None:
    row = (
        db.query(TopicTrend, Topic)
        .join(Topic, Topic.id == TopicTrend.topic_id)
        .filter(Topic.id == topic_id)
        .first()
    )
    if row is None:
        return None
    trend, topic = row
    return _build_card(db, trend, topic, recent_items_limit=10)


def _build_card(db: Session, trend: TopicTrend, topic: Topic, recent_items_limit: int = RECENT_ITEMS_LIMIT) -> dict:
    return {
        "topic_id": topic.id,
        "label": topic.label,
        "current_count": trend.current_count,
        "prior_count": trend.prior_count,
        "trend_label": trend.trend_label,
        "sparkline": _sparkline(db, topic.id),
        "recent_items": _recent_items(db, topic.id, recent_items_limit),
    }


def _sparkline(db: Session, topic_id: int) -> list[dict]:
    since = datetime.now(timezone.utc) - timedelta(weeks=SPARKLINE_WEEKS)
    week_start = func.date_trunc("week", Item.published_at)

    rows = (
        db.query(week_start.label("week_start"), func.count(func.distinct(Item.id)).label("count"))
        .join(ItemTopic, ItemTopic.item_id == Item.id)
        .filter(ItemTopic.topic_id == topic_id, Item.published_at >= since)
        .group_by(week_start)
        .order_by(week_start)
        .all()
    )
    return [{"week_start": row.week_start.date().isoformat(), "count": row.count} for row in rows]


def _recent_items(db: Session, topic_id: int, limit: int) -> list[dict]:
    rows = (
        db.query(Item, Source.name.label("source_name"))
        .join(ItemTopic, ItemTopic.item_id == Item.id)
        .join(Source, Source.id == Item.source_id)
        .filter(ItemTopic.topic_id == topic_id)
        .order_by(Item.published_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "title": item.title,
            "url": item.external_url,
            "source_name": source_name,
            "published_at": item.published_at,
        }
        for item, source_name in rows
    ]
