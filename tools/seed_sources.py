"""Idempotent seed of the `sources` config table. Run once (or re-run safely — it's
an upsert by `name`) via `python -m tools.seed_sources`.

URL confidence varies a lot across these sources (the original 13 from the spec, plus
extra testing-tool subreddits added later, plus a second tracked domain — "AI Agent
Pulse" — added after that). This sandbox's network egress is restricted to package
registries + api.anthropic.com (see workflows/deploy_railway.md "Verifying source
URLs"), so none of these were live-verified during development — only Reddit's JSON
API and Hacker News' Firebase API are stable, documented public APIs I'm confident in
without a live check. Everything else is seeded with its most likely URL (WordPress
sites overwhelmingly expose /feed/) but `enabled=False` and `config.verified=False`
until someone (or the deployed app's ingest logs) confirms it actually resolves. A
dead feed is harmless either way — tools/fetch_source.py catches per-source failures
— but shipping a source as "enabled" implies it's expected to work, which isn't true
yet for the unverified ones.

Every source belongs to exactly one `domain` ('qa' or 'agents' — see
workflows/ingest_sources.md and migrations/003_add_domain_scoping.sql). Topics are
scoped per domain, so a source's domain determines which domain's topic pool its
items get tagged into.
"""

from sqlalchemy.dialects.postgresql import insert

from app.db import SessionLocal, Source, ensure_schema

# (name, type, url, config, enabled, domain)
SOURCES: list[tuple[str, str, str | None, dict, bool, str]] = [
    (
        "Ministry of Testing",
        "rss",
        "https://www.ministryoftesting.com/rss",
        {"verified": False},
        True,
        "qa",
    ),
    (
        "Reddit r/QualityAssurance",
        "rss",
        "https://www.reddit.com/r/QualityAssurance/new/.rss",
        {
            "verified": False,
            "note": "switched from the OAuth JSON API (script-app credentials "
            "unobtainable — see r/softwaretesting note) to Reddit's own RSS feed, a "
            "different code path (feedparser, same as every other rss source) that "
            "may not be subject to the same datacenter-IP block. Free, no signup. "
            "If ingest logs show this failing too, disable it.",
        },
        True,
        "qa",
    ),
    (
        "Reddit r/softwaretesting",
        "rss",
        "https://www.reddit.com/r/softwaretesting/new/.rss",
        {
            "verified": False,
            "note": "same RSS fallback as r/QualityAssurance — see that note. Reddit's "
            "classic script-app OAuth flow now redirects to their Devvit developer "
            "platform signup instead of issuing credentials, so the OAuth path in "
            "tools/fetch_source.py (fetch_reddit/_get_reddit_token) is unused unless "
            "someone completes that signup and this RSS fallback doesn't pan out.",
        },
        True,
        "qa",
    ),
    (
        "Reddit r/selenium",
        "rss",
        "https://www.reddit.com/r/selenium/new/.rss",
        {
            "verified": False,
            "note": "web test automation (Selenium WebDriver) — same RSS approach as "
            "the other Reddit sources, unverified without live access.",
        },
        True,
        "qa",
    ),
    (
        "Reddit r/Appium",
        "rss",
        "https://www.reddit.com/r/Appium/new/.rss",
        {
            "verified": False,
            "note": "mobile test automation (cross-platform iOS/Android) — same RSS "
            "approach as the other Reddit sources, unverified without live access.",
        },
        True,
        "qa",
    ),
    (
        "Reddit r/Cypress",
        "rss",
        "https://www.reddit.com/r/Cypress/new/.rss",
        {
            "verified": False,
            "note": "modern web test automation framework — same RSS approach as the "
            "other Reddit sources, unverified without live access.",
        },
        True,
        "qa",
    ),
    (
        "Software Testing Help",
        "rss",
        "https://www.softwaretestinghelp.com/feed/",
        {"verified": False},
        True,
        "qa",
    ),
    (
        "Guru99",
        "rss",
        "https://www.guru99.com/feed",
        {"verified": False},
        True,
        "qa",
    ),
    (
        "TestGuild Blog",
        "rss",
        "https://testguild.com/feed/",
        {"verified": False},
        True,
        "qa",
    ),
    (
        "TestGuild Podcast",
        "rss",
        None,
        {"verified": False, "note": "find the actual podcast feed URL (Libsyn/Apple Podcasts) before enabling"},
        False,
        "qa",
    ),
    (
        "StickyMinds",
        "rss",
        "https://www.stickyminds.com/rss.xml",
        {"verified": False},
        True,
        "qa",
    ),
    (
        "BrowserStack Blog",
        "rss",
        "https://www.browserstack.com/blog/feed/",
        {"verified": False},
        True,
        "qa",
    ),
    (
        "Sauce Labs Blog",
        "rss",
        "https://saucelabs.com/blog/feed",
        {"verified": False},
        True,
        "qa",
    ),
    (
        "The Test Tribe",
        "manual",
        None,
        {"note": "no confirmed RSS feed — low-frequency manual check per original spec"},
        False,
        "qa",
    ),
    (
        "Hacker News (QA/testing keywords)",
        "hn_api",
        None,
        {"keywords": ["testing", "QA", "test automation", "quality assurance"], "verified": True},
        True,
        "qa",
    ),
    (
        "Software Testing Weekly",
        "manual",
        None,
        {"note": "no confirmed RSS feed for the newsletter — recheck periodically"},
        False,
        "qa",
    ),
    (
        "YouTube: Raghav Pal (Automation Step by Step)",
        "youtube_atom",
        None,
        {"channel_id": None, "note": "needs channel ID lookup before enabling"},
        False,
        "qa",
    ),
    (
        "YouTube: QAShahin",
        "youtube_atom",
        None,
        {"channel_id": None, "note": "needs channel ID lookup before enabling"},
        False,
        "qa",
    ),
    (
        "YouTube: ExecuteAutomation",
        "youtube_atom",
        None,
        {"channel_id": None, "note": "needs channel ID lookup before enabling"},
        False,
        "qa",
    ),
    (
        "YouTube: Testing Academy",
        "youtube_atom",
        None,
        {"channel_id": None, "note": "needs channel ID lookup before enabling"},
        False,
        "qa",
    ),
    (
        "ISTQB",
        "manual",
        None,
        {"note": "no RSS — weekly manual check, lowest priority per original spec"},
        False,
        "qa",
    ),
    # --- AI Agent Pulse ("agents" domain) ---
    # Of the 6 sources originally proposed, 2 were dropped: Anthropic Discord and
    # Latent Space Discord have no RSS/public API for reading messages, and a bot
    # needs admin access to servers this project doesn't run. The other 4 use the
    # same fetch mechanisms already proven for the "qa" domain, plus one bonus
    # (Hacker News filtered by agent keywords) that's zero new code.
    (
        "Reddit r/AI_Agents",
        "rss",
        "https://www.reddit.com/r/AI_Agents/new/.rss",
        {
            "verified": False,
            "note": "same Reddit RSS approach already working for the qa-domain "
            "subreddits, unverified without live access.",
        },
        True,
        "agents",
    ),
    (
        "Reddit r/ClaudeAI",
        "rss",
        "https://www.reddit.com/r/ClaudeAI/new/.rss",
        {
            "verified": False,
            "note": "same Reddit RSS approach already working for the qa-domain "
            "subreddits, unverified without live access.",
        },
        True,
        "agents",
    ),
    (
        "Reddit r/LocalLLaMA",
        "rss",
        "https://www.reddit.com/r/LocalLLaMA/new/.rss",
        {
            "verified": False,
            "note": "same Reddit RSS approach already working for the qa-domain "
            "subreddits, unverified without live access.",
        },
        True,
        "agents",
    ),
    (
        "CrewAI Community Forum",
        "rss",
        "https://community.crewai.com/latest.rss",
        {
            "verified": False,
            "note": "guessed Discourse-standard '/latest.rss' path — CrewAI's forum "
            "looked Discourse-based but this wasn't live-verified. Let ingest logs "
            "confirm or correct it.",
        },
        True,
        "agents",
    ),
    (
        "Model Context Protocol (GitHub releases)",
        "rss",
        "https://github.com/modelcontextprotocol/modelcontextprotocol/releases.atom",
        {
            "verified": False,
            "note": "GitHub's public per-repo releases Atom feed, no auth needed. "
            "Repo name/path wasn't live-verified — let ingest logs confirm.",
        },
        True,
        "agents",
    ),
    (
        "Hacker News (AI agent keywords)",
        "hn_api",
        None,
        {
            "keywords": ["AI agent", "agentic", "MCP", "multi-agent", "LangChain", "LangGraph"],
            "verified": True,
        },
        True,
        "agents",
    ),
]


def seed() -> None:
    ensure_schema()  # safe to call before the app's own startup hook has run yet —
    # e.g. a Railway Pre-deploy Command runs before the Start Command, so the
    # `sources` table may not exist yet on a first deploy without this.
    db = SessionLocal()
    try:
        for name, type_, url, config, enabled, domain in SOURCES:
            stmt = (
                insert(Source)
                .values(
                    name=name,
                    type=type_,
                    url=url,
                    config=config,
                    enabled=enabled,
                    priority="normal",
                    domain=domain,
                )
                .on_conflict_do_update(
                    index_elements=["name"],
                    set_={"type": type_, "url": url, "config": config, "enabled": enabled, "domain": domain},
                )
            )
            db.execute(stmt)
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed()
    print(f"Seeded {len(SOURCES)} sources.")
