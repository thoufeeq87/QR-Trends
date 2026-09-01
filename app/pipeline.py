import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db import Item, ItemTopic, Source, Topic
from tools import claude_tag_topics, classify_trend, fetch_source

logger = logging.getLogger(__name__)


def run_ingest(db: Session) -> dict:
    sources_checked, new_items = fetch_new_items(db)
    items_tagged = tag_untagged_items(db)
    topics_updated = classify_trend.recompute_all(db)
    return {
        "sources_checked": sources_checked,
        "new_items": new_items,
        "items_tagged": items_tagged,
        "topics_updated": topics_updated,
    }


def fetch_new_items(db: Session) -> tuple[int, int]:
    """Fetch every enabled source, insert new items (deduped by external_url).
    Returns (sources_checked, new_items). A single source failing is logged and
    skipped — it must not abort the run for the other sources."""
    sources = db.scalars(select(Source).where(Source.enabled.is_(True))).all()
    new_items = 0

    for source in sources:
        try:
            fetched = fetch_source.fetch(source)
        except Exception:
            logger.exception("fetch failed for source %s (%s)", source.name, source.type)
            continue

        new_items += _insert_items(db, source.id, fetched)
        source.last_fetched_at = datetime.now(timezone.utc)

    db.commit()
    return len(sources), new_items


def _insert_items(db: Session, source_id: int, fetched: list[fetch_source.FetchedItem]) -> int:
    if not fetched:
        return 0
    rows = [
        {
            "source_id": source_id,
            "external_url": item.external_url,
            "title": item.title,
            "summary": item.summary,
            "published_at": item.published_at,
        }
        for item in fetched
    ]
    stmt = insert(Item).values(rows).on_conflict_do_nothing(index_elements=["external_url"])
    result = db.execute(stmt)
    return result.rowcount or 0


def tag_untagged_items(db: Session) -> int:
    """Tag every item with no item_topics rows yet. See workflows/tag_topics.md."""
    untagged = db.scalars(
        select(Item).where(~Item.id.in_(select(ItemTopic.item_id)))
    ).all()
    if not untagged:
        return 0

    existing_labels = list(db.scalars(select(Topic.label)).all())
    tagged_count = 0

    for item in untagged:
        try:
            result = claude_tag_topics.tag(item.title, item.summary, existing_labels)
        except Exception:
            logger.exception("tagging failed for item %s", item.id)
            continue

        topic_ids = {_get_or_create_topic(db, label, existing_labels).id for label in result.topics}
        if topic_ids:
            stmt = (
                insert(ItemTopic)
                .values([{"item_id": item.id, "topic_id": topic_id} for topic_id in topic_ids])
                .on_conflict_do_nothing(index_elements=["item_id", "topic_id"])
            )
            db.execute(stmt)
        if result.topics:
            item.short_summary = result.summary
            tagged_count += 1
        db.commit()

    return tagged_count


def _get_or_create_topic(db: Session, label: str, existing_labels: list[str]) -> Topic:
    match = next((existing for existing in existing_labels if existing.lower() == label.lower()), None)
    if match is not None:
        return db.scalar(select(Topic).where(Topic.label == match))

    topic = Topic(label=label)
    db.add(topic)
    db.flush()
    existing_labels.append(label)
    return topic
