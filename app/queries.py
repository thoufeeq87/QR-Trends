from collections import defaultdict
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
DETAIL_RECENT_ITEMS_LIMIT = 10


def get_topic_cards(db: Session, section: str, domain: str = "qa", limit: int = 30, offset: int = 0) -> dict:
    trend_labels = SECTION_TREND_LABELS[section]

    # Fetch one extra row to cheaply detect "there are more" without a separate COUNT query.
    trends = (
        db.query(TopicTrend, Topic)
        .join(Topic, Topic.id == TopicTrend.topic_id)
        .filter(TopicTrend.trend_label.in_(trend_labels), Topic.domain == domain)
        .order_by(TopicTrend.current_count.desc(), Topic.id)
        .offset(offset)
        .limit(limit + 1)
        .all()
    )
    has_more = len(trends) > limit
    trends = trends[:limit]

    topic_ids = [topic.id for _, topic in trends]
    sparklines = _sparklines_batch(db, topic_ids)
    recent_items = _recent_items_batch(db, topic_ids, RECENT_ITEMS_LIMIT)

    cards = [_build_card(trend, topic, sparklines, recent_items) for trend, topic in trends]
    return {"topics": cards, "has_more": has_more}


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
    sparklines = _sparklines_batch(db, [topic_id])
    recent_items = _recent_items_batch(db, [topic_id], DETAIL_RECENT_ITEMS_LIMIT)
    return _build_card(trend, topic, sparklines, recent_items)


def get_last_ingested_at(db: Session, domain: str = "qa") -> datetime | None:
    return (
        db.query(func.max(Source.last_fetched_at))
        .filter(Source.enabled.is_(True), Source.domain == domain)
        .scalar()
    )


def _build_card(trend: TopicTrend, topic: Topic, sparklines: dict, recent_items: dict) -> dict:
    return {
        "topic_id": topic.id,
        "label": topic.label,
        "current_count": trend.current_count,
        "prior_count": trend.prior_count,
        "trend_label": trend.trend_label,
        "sparkline": sparklines.get(topic.id, []),
        "recent_items": recent_items.get(topic.id, []),
    }


def _sparklines_batch(db: Session, topic_ids: list[int]) -> dict[int, list[dict]]:
    if not topic_ids:
        return {}

    since = datetime.now(timezone.utc) - timedelta(weeks=SPARKLINE_WEEKS)
    week_start = func.date_trunc("week", Item.published_at)

    rows = (
        db.query(
            ItemTopic.topic_id.label("topic_id"),
            week_start.label("week_start"),
            func.count(func.distinct(Item.id)).label("count"),
        )
        .join(Item, Item.id == ItemTopic.item_id)
        .filter(ItemTopic.topic_id.in_(topic_ids), Item.published_at >= since)
        .group_by(ItemTopic.topic_id, week_start)
        .order_by(ItemTopic.topic_id, week_start)
        .all()
    )

    result: dict[int, list[dict]] = defaultdict(list)
    for row in rows:
        result[row.topic_id].append({"week_start": row.week_start.date().isoformat(), "count": row.count})
    return result


def _recent_items_batch(db: Session, topic_ids: list[int], limit: int) -> dict[int, list[dict]]:
    if not topic_ids:
        return {}

    rank = (
        func.row_number()
        .over(partition_by=ItemTopic.topic_id, order_by=Item.published_at.desc())
        .label("rank")
    )
    ranked = (
        db.query(
            ItemTopic.topic_id.label("topic_id"),
            Item.title.label("title"),
            Item.short_summary.label("short_summary"),
            Item.external_url.label("url"),
            Source.name.label("source_name"),
            Item.published_at.label("published_at"),
            rank,
        )
        .join(Item, Item.id == ItemTopic.item_id)
        .join(Source, Source.id == Item.source_id)
        .filter(ItemTopic.topic_id.in_(topic_ids))
        .subquery()
    )

    rows = db.query(ranked).filter(ranked.c.rank <= limit).order_by(ranked.c.topic_id, ranked.c.rank).all()

    result: dict[int, list[dict]] = defaultdict(list)
    for row in rows:
        result[row.topic_id].append(
            {
                "title": row.title,
                "short_summary": row.short_summary,
                "url": row.url,
                "source_name": row.source_name,
                "published_at": row.published_at,
            }
        )
    return result
