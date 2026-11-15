from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class PublishResearchInput(BaseModel):
    source_run_id: str = Field(min_length=1, max_length=100)
    model_profile_id: str | None = None
    title: str | None = Field(default=None, max_length=240)
    summary: str | None = Field(default=None, max_length=4000)
    topics: list[str] = Field(default_factory=list, max_length=12)
    domain_slug: str = Field(default="general", min_length=1, max_length=80)
    publish_report: bool = False
    anonymous: bool = False
    owner_public_id: str = Field(default="local-user", min_length=1, max_length=80)

    @field_validator("topics")
    @classmethod
    def clean_topics(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            cleaned = " ".join(value.split()).strip(" ,，；;")
            if cleaned and cleaned.casefold() not in {x.casefold() for x in result}:
                result.append(cleaned[:80])
        return result


class ActorInput(BaseModel):
    user_public_id: str = Field(default="local-user", min_length=1, max_length=80)
    event_id: str | None = Field(default=None, max_length=100)


class PinInput(BaseModel):
    pinned: bool = True


class ChatInput(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    model_profile_id: str | None = None
    days: int = Field(default=30, ge=1, le=365)
    domain_slug: str | None = Field(default=None, max_length=80)
    data_source: Literal["local", "openalex"] = "local"


class QueryPlan(BaseModel):
    intent: Literal[
        "rank_topics", "topic_trend", "compare_topics", "related_topics",
        "list_researches", "domain_summary"
    ] = "rank_topics"
    metric: Literal["heat", "growth", "research_count", "views", "likes"] = "heat"
    days: int = Field(default=30, ge=1, le=365)
    limit: int = Field(default=10, ge=1, le=30)
    domain_slug: str | None = Field(default=None, max_length=80)
    topics: list[str] = Field(default_factory=list, max_length=5)
