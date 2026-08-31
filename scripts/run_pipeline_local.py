"""Local Phase-A validation: exercise the DB layer, real Claude tagging, and trend
classification end-to-end without a live network fetch.

Why not just call app.pipeline.fetch_new_items()? This sandbox's network egress is
restricted to package registries + api.anthropic.com — Reddit/RSS/HN are unreachable
here (see the note in tools/seed_sources.py). The fetch step itself (tools/fetch_source.py)
is written against each source's documented API/feed shape and gets proven for real
once deployed to Railway, which has normal internet access.

This script instead:
  1. Seeds the sources table (tools.seed_sources)
  2. Inserts a handful of realistic fixture items (standing in for a live fetch),
     spread across the last 30 days to exercise every trend bucket
  3. Runs the REAL Claude tagging call against a few of them
  4. Manually assigns topics to the rest, so trend classification's math (new /
     trending / stable / declining) is verified deterministically rather than
     depending on how an LLM happens to label things this run
  5. Runs trend classification and prints the result
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy.dialects.postgresql import insert

from app.db import Item, ItemTopic, SessionLocal, Source, Topic, TopicTrend, ensure_schema
from app.pipeline import tag_untagged_items
from tools import classify_trend, seed_sources

now = datetime.now(timezone.utc)


def days_ago(n: float) -> datetime:
    return now - timedelta(days=n)


# Items Claude will actually tag (validates the real API call + structured output).
CLAUDE_TAGGED_ITEMS = [
    ("https://example-fixture.test/1", "Playwright 1.50 released with new trace viewer features", days_ago(1)),
    ("https://example-fixture.test/2", "Why teams are adopting Playwright over Selenium in 2026", days_ago(2)),
    ("https://example-fixture.test/3", "Using Claude to auto-generate test cases from user stories", days_ago(1)),
    ("https://example-fixture.test/4", "A beginner's guide to manual exploratory testing", days_ago(20)),
]

# Items with topics assigned directly, to deterministically exercise every
# classify_trend.py bucket regardless of what Claude happens to label things.
FIXED_TOPIC_SCENARIOS = {
    # topic label -> list of (days_ago, count) description; we just generate N items per bucket
    "fixture: new topic": [(1, 3)],  # 3 mentions this week, none before -> new
    "fixture: trending topic": [(1, 4), (10, 1)],  # 4 this week vs weekly rate ~0.3 -> trending
    "fixture: stable topic": [(2, 1), (10, 4)],  # 1 this week vs weekly rate ~1.2 -> stable
    "fixture: declining topic": [(20, 5)],  # 0 this week, 5 in prior window -> declining
}


def seed_fixed_topic_items(db) -> None:
    source = db.query(Source).filter_by(name="Reddit r/softwaretesting").one()
    url_counter = 100

    for label, buckets in FIXED_TOPIC_SCENARIOS.items():
        topic = db.query(Topic).filter_by(label=label).one_or_none()
        if topic is None:
            topic = Topic(label=label)
            db.add(topic)
            db.flush()

        for age_days, count in buckets:
            for _ in range(count):
                url_counter += 1
                item = Item(
                    source_id=source.id,
                    external_url=f"https://example-fixture.test/{url_counter}",
                    title=f"Fixture item for {label}",
                    summary=None,
                    published_at=days_ago(age_days),
                )
                db.add(item)
                db.flush()
                db.execute(
                    insert(ItemTopic)
                    .values(item_id=item.id, topic_id=topic.id)
                    .on_conflict_do_nothing(index_elements=["item_id", "topic_id"])
                )
    db.commit()


def main() -> None:
    ensure_schema()
    seed_sources.seed()

    db = SessionLocal()
    try:
        source = db.query(Source).filter_by(name="Reddit r/softwaretesting").one()
        for url, title, published_at in CLAUDE_TAGGED_ITEMS:
            stmt = (
                insert(Item)
                .values(source_id=source.id, external_url=url, title=title, published_at=published_at)
                .on_conflict_do_nothing(index_elements=["external_url"])
            )
            db.execute(stmt)
        db.commit()

        print("Tagging items via the real Claude API...")
        tagged = tag_untagged_items(db)
        print(f"  tagged {tagged} item(s)")

        print("Seeding fixed-topic items for deterministic trend classification...")
        seed_fixed_topic_items(db)

        print("Classifying trends...")
        updated = classify_trend.recompute_all(db)
        print(f"  {updated} topic_trends row(s) written")

        print("\n--- item_topics from Claude tagging ---")
        claude_items = db.query(Item).filter(Item.external_url.in_([u for u, _, _ in CLAUDE_TAGGED_ITEMS])).order_by(Item.id)
        for item in claude_items:
            labels = [
                topic.label
                for topic, in db.query(Topic.label)
                .join(ItemTopic, ItemTopic.topic_id == Topic.id)
                .filter(ItemTopic.item_id == item.id)
                .all()
            ]
            print(f"  [{item.title[:60]}] -> {labels}")

        print("\n--- topic_trends ---")
        for topic in db.query(Topic).order_by(Topic.id):
            trend = db.get(TopicTrend, topic.id)
            if trend:
                print(
                    f"  {topic.label!r}: current={trend.current_count} prior={trend.prior_count} "
                    f"-> {trend.trend_label}"
                )
    finally:
        db.close()


if __name__ == "__main__":
    main()
