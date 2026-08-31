"""Extract QA/testing topic labels from an item via Claude. See workflows/tag_topics.md.

Model choice (claude-opus-5) is a named constant — deliberately, not accidentally,
change it if per-item cost at real volume warrants a cheaper model.
"""

import anthropic
from pydantic import BaseModel

MODEL = "claude-opus-5"
MAX_TOPICS = 3

SYSTEM_TEMPLATE = """You tag articles, posts, and videos for a software QA/testing \
trend tracker. Given a title and summary, extract 1-{max_topics} short topic labels \
(2-4 words each, e.g. "AI test generation", "Playwright", "manual testing decline").

Prefer reusing one of these existing labels if it genuinely applies — do not invent a \
near-duplicate of an existing label:
{existing_labels}

Only propose a new label when none of the existing ones fit. Return only topics \
clearly relevant to software QA/testing — if the content isn't QA/testing-related, \
return an empty list."""


class TopicExtraction(BaseModel):
    topics: list[str]


def tag(title: str, summary: str | None, existing_labels: list[str]) -> list[str]:
    client = anthropic.Anthropic()
    system = SYSTEM_TEMPLATE.format(
        max_topics=MAX_TOPICS,
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
    return response.parsed_output.topics[:MAX_TOPICS]
