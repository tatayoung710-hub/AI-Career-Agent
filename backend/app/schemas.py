"""Public core request models; owner identifiers always come from authentication."""

import re
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.ai.schemas import ResumeContent


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class AuthInput(StrictInput):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email address")
        return value.lower()


class ProfileUpdate(StrictInput):
    name: str | None = Field(default=None, max_length=100)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=100)
    location: str | None = Field(default=None, max_length=200)
    target_roles: list[str] | None = Field(default=None, max_length=30)
    target_locations: list[str] | None = Field(default=None, max_length=30)
    summary: str | None = Field(default=None, max_length=10000)
    preferences: dict[str, Any] | None = None


class FactCreate(StrictInput):
    kind: Literal["education", "experience", "project", "skill", "interest", "achievement"]
    title: str = Field(default="", max_length=255)
    content: str = Field(min_length=1, max_length=12000)
    tags: list[str] = Field(default_factory=list, max_length=50)
    source_text: str = Field(default="", max_length=12000)
    details: dict[str, Any] = Field(default_factory=dict)
    document_id: str | None = None
    supersedes_id: str | None = None


class SourceCreate(StrictInput):
    name: str = Field(min_length=1, max_length=200)
    kind: Literal["website", "rss", "feishu", "spreadsheet", "wechat", "mini_program", "email"] = (
        "website"
    )
    url: str = Field(default="", max_length=3000)
    notes: str = Field(default="", max_length=10000)


class SourceUpdate(StrictInput):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    kind: (
        Literal["website", "rss", "feishu", "spreadsheet", "wechat", "mini_program", "email"] | None
    ) = None
    url: str | None = Field(default=None, max_length=3000)
    notes: str | None = Field(default=None, max_length=10000)


class JobCreate(StrictInput):
    company: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=255)
    location: str = Field(default="", max_length=255)
    industry: str = Field(default="", max_length=200)
    jd_text: str = Field(min_length=1, max_length=100000)
    jd_complete: bool = True
    requirements: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    salary_text: str = Field(default="", max_length=255)
    source_id: str | None = None
    source_url: str = Field(default="", max_length=3000)
    published_at: date | None = None
    deadline: date | None = None
    status: Literal["active", "closed", "archived"] = "active"


class JobUpdate(StrictInput):
    company: str | None = Field(default=None, min_length=1, max_length=255)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    industry: str | None = Field(default=None, max_length=200)
    jd_text: str | None = Field(default=None, min_length=1, max_length=100000)
    jd_complete: bool | None = None
    requirements: list[dict[str, Any]] | None = Field(default=None, max_length=100)
    salary_text: str | None = Field(default=None, max_length=255)
    source_id: str | None = None
    source_url: str | None = Field(default=None, max_length=3000)
    published_at: date | None = None
    deadline: date | None = None
    status: Literal["active", "closed", "archived"] | None = None
    version_number: int = Field(ge=1)


class ResumeCreate(StrictInput):
    name: str = Field(min_length=1, max_length=200)
    language: Literal["zh", "en"] = "zh"
    style: str = Field(default="professional", max_length=50)
    template: Literal["classic", "compact"] = "classic"


class ResumeVersionCreate(StrictInput):
    content: ResumeContent
    parent_version_id: str | None = None
    job_id: str | None = None
    language: Literal["zh", "en"] | None = None
    style: str | None = Field(default=None, max_length=50)
    template: Literal["classic", "compact"] | None = None


ApplicationStatus = Literal[
    "pending", "applied", "hr_chat", "interview_1", "interview_2", "offer", "rejected", "withdrawn"
]


class ApplicationCreate(StrictInput):
    job_id: str
    resume_version_id: str | None = None
    attempt_no: int = Field(default=1, ge=1, le=100)
    status: ApplicationStatus = "pending"
    applied_at: date | None = None
    hr_name: str = Field(default="", max_length=100)
    hr_contact: str = Field(default="", max_length=255)
    notes: str = Field(default="", max_length=12000)


class ApplicationUpdate(StrictInput):
    version: int = Field(ge=1)
    status: ApplicationStatus | None = None
    applied_at: date | None = None
    hr_name: str | None = Field(default=None, max_length=100)
    hr_contact: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=12000)
    resume_version_id: str | None = None
