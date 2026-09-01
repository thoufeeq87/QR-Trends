"""Extract QA/testing topic labels + a short summary from an item via Claude. See
workflows/tag_topics.md.

Model choice (claude-opus-5) is a named constant — deliberately, not accidentally,
change it if per-item cost at real volume warrants a cheaper model.
"""

import anthropic
from pydantic import BaseModel

MODEL = "claude-opus-5"
MAX_TOPICS = 3
MAX_SUMMARY_WORDS = 10

SYSTEM_TEMPLATE = """You tag articles, posts, and videos for a software QA/testing \
trend tracker. Given a title and summary, do two things:

1. Extract 1-{max_topics} short topic labels (2-4 words each, e.g. "AI test \
generation", "Playwright", "manual testing decline").

Prefer reusing one of these existing labels if it genuinely applies — do not invent a \
near-duplicate of an existing label:
{existing_labels}

Only propose a new label when none of the existing ones fit. Return only topics \
clearly relevant to software QA/testing — if the content isn't QA/testing-related, \
return an empty list.

2. Write a plain-language summary of what the item is actually about, in at most \
{max_summary_words} words. Paraphrase and condense — don't just truncate the title \
verbatim, especially for long or rambling forum/Reddit post titles phrased as \
questions."""


class TopicExtraction(BaseModel):
    topics: list[str]
    summary: str


def tag(title: str, summary: str | None, existing_labels: list[str]) -> TopicExtraction:
    client = anthropic.Anthropic()
    system = SYSTEM_TEMPLATE.format(
        max_topics=MAX_TOPICS,
        max_summary_words=MAX_SUMMARY_WORDS,
        existing_labels=", ".join(sorted(existing_labels)) or "(none yet)",
    )
    content = f"Title: {title}\nSummary: {summary or '(none)'}"

    response = client.messages.parse(
        model=MODEL,
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": content}],
        output_format=TopicExtraction,
    )
    result = response.parsed_output
    return TopicExtraction(topics=result.topics[:MAX_TOPICS], summary=result.summary)
