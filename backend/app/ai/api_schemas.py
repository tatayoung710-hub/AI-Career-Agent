"""Validated request and response contracts for interactive AI features."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.ai.schemas import ResumeContent


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ChatInput(Input):
    message: str = Field(min_length=1, max_length=12000)
    session_id: str | None = None
    job_id: str | None = None


class ReviewInput(Input):
    kind: Literal["resume", "interview", "hr_reply"]
    text: str = Field(min_length=1, max_length=20000)
    job_id: str | None = None
    question: str = Field(default="", max_length=10000)


class DraftInput(Input):
    job_id: str
    channel: Literal["boss", "email", "linkedin", "wechat"]
    purpose: Literal["opening", "follow_up", "networking"] = "opening"
    language: Literal["zh", "en"] = "zh"


class ExtractInput(Input):
    text: str = Field(min_length=1, max_length=50000)
    source_name: str = Field(default="手动粘贴", max_length=200)
    source_url: str = Field(default="", max_length=3000)


class MatchInput(Input):
    job_id: str


class TailorInput(Input):
    job_id: str
    language: Literal["zh", "en"] = "zh"
    style: str = Field(default="professional", max_length=50)
    template: Literal["classic", "compact"] = "classic"


class ValidateInput(Input):
    resume_id: str
    version_id: str


class Issue(BaseModel):
    quote: str
    problem: str
    why: str
    suggestion: str


class ReviewOutput(BaseModel):
    summary: str
    issues: list[Issue]
    possible_hr_concerns: list[str]
    professionalism_notes: list[str]
    improved_answer: str
    follow_up_questions: list[str]


class ChatOutput(BaseModel):
    reply: str
    follow_up_questions: list[str]


class RequirementResult(BaseModel):
    requirement: str
    weight: int = Field(ge=1, le=5)
    hard_requirement: bool
    support: Literal["supported", "missing", "needs_verification"]
    evidence_fact_ids: list[str]
    rationale: str


class MatchOutput(BaseModel):
    requirements: list[RequirementResult]
    strengths: list[str]
    gaps: list[str]
    suggestions: list[str]
    summary: str


class ResumeOutput(BaseModel):
    resume: ResumeContent


class ClaimAuditItem(BaseModel):
    statement_path: str
    supported: bool
    rationale: str


class ResumeAudit(BaseModel):
    claims: list[ClaimAuditItem]


class ExtractedJob(BaseModel):
    company: str = ""
    title: str
    location: str = ""
    industry: str = ""
    salary_text: str = ""
    jd_text: str
    jd_complete: bool
    requirements: list[str]
    source_url: str = ""


class JobExtraction(BaseModel):
    jobs: list[ExtractedJob]


class DraftOutput(BaseModel):
    content: str
    fact_ids: list[str]
    notes: list[str]
