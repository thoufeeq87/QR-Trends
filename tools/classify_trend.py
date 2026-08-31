"""Recompute topic_trends. See workflows/classify_trends.md for the rule."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import Item, ItemTopic, Topic, TopicTrend

CURRENT_WINDOW_DAYS = 7
PRIOR_WINDOW_DAYS = 30
PRIOR_WINDOW_LENGTH = PRIOR_WINDOW_DAYS - CURRENT_WINDOW_DAYS  # 23-day prior window

TRENDING_MULTIPLIER = 1.5
DECLINING_MULTIPLIER = 0.5
TRENDING_MIN_COUNT = 2


def recompute_all(db: Session) -> int:
    now = datetime.now(timezone.utc)
    current_since = now - timedelta(days=CURRENT_WINDOW_DAYS)
    prior_since = now - timedelta(days=PRIOR_WINDOW_DAYS)

    topic_ids = [
        row[0]
        for row in db.query(Topic.id)
        .join(ItemTopic, ItemTopic.topic_id == Topic.id)
        .join(Item, Item.id == ItemTopic.item_id)
        .filter(Item.published_at >= prior_since)
        .distinct()
        .all()
    ]

    written = 0
    for topic_id in topic_ids:
        current_count = _count_mentions(db, topic_id, current_since, now)
        prior_count = _count_mentions(db, topic_id, prior_since, current_since)
        trend_label = _classify(current_count, prior_count)

        trend = db.get(TopicTrend, topic_id)
        if trend is None:
            trend = TopicTrend(topic_id=topic_id)
            db.add(trend)
        trend.current_count = current_count
        trend.prior_count = prior_count
        trend.trend_label = trend_label
        trend.last_updated = now
        written += 1

    db.commit()
    return written


def _count_mentions(db: Session, topic_id: int, since: datetime, until: datetime) -> int:
    return (
        db.query(func.count(func.distinct(Item.id)))
        .join(ItemTopic, ItemTopic.item_id == Item.id)
        .filter(ItemTopic.topic_id == topic_id, Item.published_at >= since, Item.published_at < until)
        .scalar()
        or 0
    )


def _classify(current_count: int, prior_count: int) -> str:
    prior_weekly_rate = prior_count * CURRENT_WINDOW_DAYS / PRIOR_WINDOW_LENGTH

    if prior_count == 0 and current_count > 0:
        return "new"
    if current_count >= prior_weekly_rate * TRENDING_MULTIPLIER and current_count >= TRENDING_MIN_COUNT:
        return "trending"
    if current_count <= prior_weekly_rate * DECLINING_MULTIPLIER:
        return "declining"
    return "stable"
