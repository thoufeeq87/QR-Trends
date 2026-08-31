from datetime import datetime

from pydantic import BaseModel


class SparklinePoint(BaseModel):
    week_start: str
    count: int


class RecentItem(BaseModel):
    title: str
    url: str
    source_name: str
    published_at: datetime


class TopicCard(BaseModel):
    topic_id: int
    label: str
    current_count: int
    prior_count: int
    trend_label: str
    sparkline: list[SparklinePoint]
    recent_items: list[RecentItem]


class IngestSummary(BaseModel):
    sources_checked: int
    new_items: int
    items_tagged: int
    topics_updated: int
