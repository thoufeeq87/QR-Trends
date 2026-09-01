"""Fetch new items for a single source. See workflows/ingest_sources.md.

Each fetch_* function returns a list of FetchedItem, normalized regardless of the
source's underlying format. Network calls are isolated here so app/pipeline.py and
tests/fixtures never need to know the difference between an RSS feed and a JSON API.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser
import requests

from app.config import REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET

USER_AGENT = "qa-pulse/1.0 (topic-trend tracker; contact via GitHub repo)"
HN_BASE = "https://hacker-news.firebaseio.com/v0"
HN_STORY_SLICE = 200
REQUEST_TIMEOUT = 15
REDDIT_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
REDDIT_OAUTH_BASE = "https://oauth.reddit.com"
REDDIT_TOKEN_REFRESH_MARGIN = 60  # seconds before expiry to proactively refresh

_reddit_token_cache: dict[str, object] = {"token": None, "expires_at": 0.0}


@dataclass
class FetchedItem:
    external_url: str
    title: str
    summary: str | None
    published_at: datetime


def fetch(source) -> list[FetchedItem]:
    """Dispatch by source.type. `source` is an app.db.Source (or any object with
    the same .type/.url/.config attributes)."""
    if source.type == "rss" or source.type == "youtube_atom":
        return fetch_feed(source.url)
    if source.type == "reddit_json":
        return fetch_reddit(source.config["subreddit"])
    if source.type == "hn_api":
        return fetch_hn(source.config.get("keywords", []))
    if source.type == "manual":
        return []
    raise ValueError(f"unknown source type: {source.type}")


def fetch_feed(url: str) -> list[FetchedItem]:
    """RSS 2.0 or Atom — feedparser handles both. Covers blog/podcast RSS and
    YouTube's Atom channel feeds identically."""
    parsed = feedparser.parse(url, agent=USER_AGENT)
    items = []
    for entry in parsed.entries:
        link = entry.get("link")
        title = entry.get("title")
        if not link or not title:
            continue
        items.append(
            FetchedItem(
                external_url=link,
                title=title,
                summary=_clean_summary(entry.get("summary")),
                published_at=_parse_feed_date(entry),
            )
        )
    return items


def fetch_reddit(subreddit: str) -> list[FetchedItem]:
    """Reddit's OAuth API. The old anonymous reddit.com/.../new.json endpoint gets a
    hard 403 from datacenter/cloud-host IPs regardless of User-Agent — see
    workflows/ingest_sources.md Edge cases. Requires REDDIT_CLIENT_ID/SECRET."""
    url = f"{REDDIT_OAUTH_BASE}/r/{subreddit}/new"
    headers = {"User-Agent": USER_AGENT, "Authorization": f"Bearer {_get_reddit_token()}"}
    resp = requests.get(url, headers=headers, params={"limit": 25}, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    children = resp.json()["data"]["children"]
    items = []
    for child in children:
        post = child["data"]
        items.append(
            FetchedItem(
                external_url=f"https://www.reddit.com{post['permalink']}",
                title=post["title"],
                summary=_clean_summary(post.get("selftext")) or None,
                published_at=datetime.fromtimestamp(post["created_utc"], tz=timezone.utc),
            )
        )
    return items


def _get_reddit_token() -> str:
    """Client-credentials OAuth token, cached in-process until near expiry."""
    now = time.monotonic()
    if _reddit_token_cache["token"] and now < _reddit_token_cache["expires_at"]:
        return _reddit_token_cache["token"]

    resp = requests.post(
        REDDIT_TOKEN_URL,
        auth=(REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET),
        data={"grant_type": "client_credentials"},
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    payload = resp.json()

    _reddit_token_cache["token"] = payload["access_token"]
    _reddit_token_cache["expires_at"] = now + payload["expires_in"] - REDDIT_TOKEN_REFRESH_MARGIN
    return _reddit_token_cache["token"]


def fetch_hn(keywords: list[str]) -> list[FetchedItem]:
    """No keyword-search endpoint exists, so pull a bounded slice of new story IDs
    and filter titles client-side. See workflows/ingest_sources.md Edge cases."""
    ids = requests.get(f"{HN_BASE}/newstories.json", timeout=REQUEST_TIMEOUT).json()[:HN_STORY_SLICE]
    keywords_lower = [k.lower() for k in keywords]
    items = []
    for story_id in ids:
        story = requests.get(f"{HN_BASE}/item/{story_id}.json", timeout=REQUEST_TIMEOUT).json()
        if not story or story.get("type") != "story":
            continue
        title = story.get("title", "")
        if not any(kw in title.lower() for kw in keywords_lower):
            continue
        url = story.get("url") or f"https://news.ycombinator.com/item?id={story_id}"
        items.append(
            FetchedItem(
                external_url=url,
                title=title,
                summary=None,
                published_at=datetime.fromtimestamp(story["time"], tz=timezone.utc),
            )
        )
    return items


def _clean_summary(raw: str | None) -> str | None:
    if not raw:
        return None
    return raw.strip()[:2000] or None


def _parse_feed_date(entry) -> datetime:
    for key in ("published", "updated"):
        value = entry.get(key)
        if value:
            try:
                return parsedate_to_datetime(value)
            except (TypeError, ValueError):
                pass
    return datetime.now(timezone.utc)
