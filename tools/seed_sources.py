"""Idempotent seed of the `sources` config table. Run once (or re-run safely — it's
an upsert by `name`) via `python -m tools.seed_sources`.

URL confidence varies a lot across these 13 sources. This sandbox's network egress is
restricted to package registries + api.anthropic.com (see workflows/deploy_railway.md
"Verifying source URLs"), so none of these were live-verified during development —
only Reddit's JSON API and Hacker News' Firebase API are stable, documented public
APIs I'm confident in without a live check. Everything else is seeded with its most
likely URL (WordPress sites overwhelmingly expose /feed/) but `enabled=False` and
`config.verified=False` until someone (or the deployed app's ingest logs) confirms it
actually resolves. A dead feed is harmless either way — tools/fetch_source.py catches
per-source failures — but shipping a source as "enabled" implies it's expected to
work, which isn't true yet for the unverified ones.
"""

from sqlalchemy.dialects.postgresql import insert

from app.db import SessionLocal, Source, ensure_schema

# (name, type, url, config, enabled)
SOURCES: list[tuple[str, str, str | None, dict, bool]] = [
    (
        "Ministry of Testing",
        "rss",
        "https://www.ministryoftesting.com/rss",
        {"verified": False},
        False,
    ),
    (
        "Reddit r/QualityAssurance",
        "reddit_json",
        None,
        {"subreddit": "QualityAssurance", "verified": True},
        True,
    ),
    (
        "Reddit r/softwaretesting",
        "reddit_json",
        None,
        {"subreddit": "softwaretesting", "verified": True},
        True,
    ),
    (
        "Software Testing Help",
        "rss",
        "https://www.softwaretestinghelp.com/feed/",
        {"verified": False},
        False,
    ),
    (
        "Guru99",
        "rss",
        "https://www.guru99.com/feed",
        {"verified": False},
        False,
    ),
    (
        "TestGuild Blog",
        "rss",
        "https://testguild.com/feed/",
        {"verified": False},
        False,
    ),
    (
        "TestGuild Podcast",
        "rss",
        None,
        {"verified": False, "note": "find the actual podcast feed URL (Libsyn/Apple Podcasts) before enabling"},
        False,
    ),
    (
        "StickyMinds",
        "rss",
        "https://www.stickyminds.com/rss.xml",
        {"verified": False},
        False,
    ),
    (
        "BrowserStack Blog",
        "rss",
        "https://www.browserstack.com/blog/feed/",
        {"verified": False},
        False,
    ),
    (
        "Sauce Labs Blog",
        "rss",
        "https://saucelabs.com/blog/feed",
        {"verified": False},
        False,
    ),
    (
        "The Test Tribe",
        "manual",
        None,
        {"note": "no confirmed RSS feed — low-frequency manual check per original spec"},
        False,
    ),
    (
        "Hacker News (QA/testing keywords)",
        "hn_api",
        None,
        {"keywords": ["testing", "QA", "test automation", "quality assurance"], "verified": True},
        True,
    ),
    (
        "Software Testing Weekly",
        "manual",
        None,
        {"note": "no confirmed RSS feed for the newsletter — recheck periodically"},
        False,
    ),
    (
        "YouTube: Raghav Pal (Automation Step by Step)",
        "youtube_atom",
        None,
        {"channel_id": None, "note": "needs channel ID lookup before enabling"},
        False,
    ),
    (
        "YouTube: QAShahin",
        "youtube_atom",
        None,
        {"channel_id": None, "note": "needs channel ID lookup before enabling"},
        False,
    ),
    (
        "YouTube: ExecuteAutomation",
        "youtube_atom",
        None,
        {"channel_id": None, "note": "needs channel ID lookup before enabling"},
        False,
    ),
    (
        "YouTube: Testing Academy",
        "youtube_atom",
        None,
        {"channel_id": None, "note": "needs channel ID lookup before enabling"},
        False,
    ),
    (
        "ISTQB",
        "manual",
        None,
        {"note": "no RSS — weekly manual check, lowest priority per original spec"},
        False,
    ),
]


def seed() -> None:
    ensure_schema()  # safe to call before the app's own startup hook has run yet —
    # e.g. a Railway Pre-deploy Command runs before the Start Command, so the
    # `sources` table may not exist yet on a first deploy without this.
    db = SessionLocal()
    try:
        for name, type_, url, config, enabled in SOURCES:
            stmt = (
                insert(Source)
                .values(name=name, type=type_, url=url, config=config, enabled=enabled, priority="normal")
                .on_conflict_do_update(
                    index_elements=["name"],
                    set_={"type": type_, "url": url, "config": config, "enabled": enabled},
                )
            )
            db.execute(stmt)
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed()
    print(f"Seeded {len(SOURCES)} sources.")
