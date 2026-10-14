"""Relational ownership, immutable evidence revisions and durable execution ledgers."""

from datetime import date, datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    true,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def new_id() -> str:
    return str(uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


JSON_VALUE = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class Owned:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Profile(Owned, Base):
    __tablename__ = "profiles"
    __table_args__ = (UniqueConstraint("user_id"), UniqueConstraint("user_id", "id"))
    name: Mapped[str] = mapped_column(String(100), default="")
    email: Mapped[str] = mapped_column(String(254), default="")
    phone: Mapped[str] = mapped_column(String(100), default="")
    location: Mapped[str] = mapped_column(String(200), default="")
    target_roles: Mapped[list] = mapped_column(JSON_VALUE, default=list)
    target_locations: Mapped[list] = mapped_column(JSON_VALUE, default=list)
    summary: Mapped[str] = mapped_column(Text, default="")
    preferences: Mapped[dict] = mapped_column(JSON_VALUE, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Document(Owned, Base):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("user_id", "id"),)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(150))
    storage_path: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    parsed_text: Mapped[str] = mapped_column(Text, default="")
    parser_version: Mapped[str] = mapped_column(String(50), default="v1")
    error: Mapped[str | None] = mapped_column(Text)


class Fact(Owned, Base):
    __tablename__ = "facts"
    __table_args__ = (
        UniqueConstraint("user_id", "id"),
        UniqueConstraint("user_id", "lineage_id", "revision_number"),
        ForeignKeyConstraint(["user_id", "document_id"], ["documents.user_id", "documents.id"]),
        ForeignKeyConstraint(["user_id", "supersedes_id"], ["facts.user_id", "facts.id"]),
        CheckConstraint("revision_number >= 1", name="positive_revision"),
        CheckConstraint(
            "kind IN ('education','experience','project','skill','interest','achievement')",
            name="kind",
        ),
    )
    lineage_id: Mapped[str] = mapped_column(String(36), default=new_id)
    revision_number: Mapped[int] = mapped_column(Integer, default=1)
    supersedes_id: Mapped[str | None] = mapped_column(String(36))
    document_id: Mapped[str | None] = mapped_column(String(36))
    kind: Mapped[str] = mapped_column(String(30), default="experience")
    title: Mapped[str] = mapped_column(String(255), default="")
    content: Mapped[str] = mapped_column(Text)
    tags: Mapped[list] = mapped_column(JSON_VALUE, default=list)
    source_text: Mapped[str] = mapped_column(Text, default="")
    details: Mapped[dict] = mapped_column(JSON_VALUE, default=dict)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Source(Owned, Base):
    __tablename__ = "sources"
    __table_args__ = (UniqueConstraint("user_id", "id"),)
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(50), default="website")
    url: Mapped[str] = mapped_column(Text, default="")
    capability: Mapped[str] = mapped_column(String(40), default="prepare_open")
    notes: Mapped[str] = mapped_column(Text, default="")
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    new_jobs_count: Mapped[int] = mapped_column(Integer, default=0)
    sync_task_id: Mapped[str | None] = mapped_column(String(36))
    archived: Mapped[bool] = mapped_column(Boolean, default=False)


class Job(Owned, Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("user_id", "id"),
        ForeignKeyConstraint(["user_id", "source_id"], ["sources.user_id", "sources.id"]),
        CheckConstraint("status IN ('active','closed','archived')", name="status"),
    )
    company: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(255))
    location: Mapped[str] = mapped_column(String(255), default="")
    industry: Mapped[str] = mapped_column(String(200), default="")
    jd_text: Mapped[str] = mapped_column(Text)
    jd_complete: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    requirements: Mapped[list] = mapped_column(JSON_VALUE, default=list)
    salary_text: Mapped[str] = mapped_column(String(255), default="")
    source_id: Mapped[str | None] = mapped_column(String(36))
    source_url: Mapped[str] = mapped_column(Text, default="")
    published_at: Mapped[date | None] = mapped_column(Date)
    deadline: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30), default="active")
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class JobVersion(Owned, Base):
    __tablename__ = "job_versions"
    __table_args__ = (
        UniqueConstraint("user_id", "id"),
        UniqueConstraint("user_id", "job_id", "id"),
        UniqueConstraint("job_id", "version_number"),
        ForeignKeyConstraint(["user_id", "job_id"], ["jobs.user_id", "jobs.id"]),
        CheckConstraint("version_number >= 1", name="positive_version"),
    )
    job_id: Mapped[str] = mapped_column(String(36))
    version_number: Mapped[int] = mapped_column(Integer)
    jd_text: Mapped[str] = mapped_column(Text)
    requirements: Mapped[list] = mapped_column(JSON_VALUE, default=list)
    snapshot: Mapped[dict] = mapped_column(JSON_VALUE, default=dict)
    extraction_version: Mapped[str] = mapped_column(String(50), default="manual-v1")


class JobSourceRecord(Owned, Base):
    __tablename__ = "job_source_records"
    __table_args__ = (
        UniqueConstraint("user_id", "id"),
        UniqueConstraint("user_id", "source_key", "external_key"),
        ForeignKeyConstraint(["user_id", "job_id"], ["jobs.user_id", "jobs.id"]),
        ForeignKeyConstraint(["user_id", "source_id"], ["sources.user_id", "sources.id"]),
    )
    job_id: Mapped[str] = mapped_column(String(36))
    source_id: Mapped[str | None] = mapped_column(String(36))
    source_key: Mapped[str] = mapped_column(String(200))
    external_key: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(Text, default="")
    raw_text: Mapped[str] = mapped_column(Text, default="")
    published_at: Mapped[date | None] = mapped_column(Date)


class Resume(Owned, Base):
    __tablename__ = "resumes"
    __table_args__ = (UniqueConstraint("user_id", "id"),)
    name: Mapped[str] = mapped_column(String(200))
    language: Mapped[str] = mapped_column(String(10), default="zh")
    style: Mapped[str] = mapped_column(String(50), default="professional")
    template: Mapped[str] = mapped_column(String(50), default="classic")


class ResumeVersion(Owned, Base):
    __tablename__ = "resume_versions"
    __table_args__ = (
        UniqueConstraint("user_id", "id"),
        UniqueConstraint("user_id", "resume_id", "id"),
        UniqueConstraint("resume_id", "version_number"),
        ForeignKeyConstraint(["user_id", "resume_id"], ["resumes.user_id", "resumes.id"]),
        ForeignKeyConstraint(
            ["user_id", "parent_version_id"], ["resume_versions.user_id", "resume_versions.id"]
        ),
        ForeignKeyConstraint(
            ["user_id", "job_id", "job_version_id"],
            ["job_versions.user_id", "job_versions.job_id", "job_versions.id"],
        ),
        CheckConstraint("version_number >= 1", name="positive_version"),
        CheckConstraint("language IN ('zh','en')", name="language"),
        CheckConstraint(
            "evidence_status IN ('pending','validated','rejected')", name="evidence_status"
        ),
    )
    resume_id: Mapped[str] = mapped_column(String(36))
    version_number: Mapped[int] = mapped_column(Integer)
    parent_version_id: Mapped[str | None] = mapped_column(String(36))
    job_id: Mapped[str | None] = mapped_column(String(36))
    job_version_id: Mapped[str | None] = mapped_column(String(36))
    language: Mapped[str] = mapped_column(String(10), default="zh")
    style: Mapped[str] = mapped_column(String(50), default="professional")
    template: Mapped[str] = mapped_column(String(50), default="classic")
    schema_version: Mapped[str] = mapped_column(String(30), default="v1")
    content: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE)
    facts_snapshot: Mapped[list] = mapped_column(JSON_VALUE, default=list)
    job_snapshot: Mapped[dict] = mapped_column(JSON_VALUE, default=dict)
    evidence_status: Mapped[str] = mapped_column(String(30), default="pending")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approval_source: Mapped[str] = mapped_column(String(40), default="manual")
    approval_policy_snapshot: Mapped[dict] = mapped_column(JSON_VALUE, default=dict)
    export_status: Mapped[str] = mapped_column(String(30), default="not_requested")
    export_path: Mapped[str | None] = mapped_column(Text)


class ResumeEvidence(Owned, Base):
    __tablename__ = "resume_evidence"
    __table_args__ = (
        UniqueConstraint("user_id", "id"),
        UniqueConstraint("resume_version_id", "statement_path", "fact_id"),
        ForeignKeyConstraint(
            ["user_id", "resume_version_id"], ["resume_versions.user_id", "resume_versions.id"]
        ),
        ForeignKeyConstraint(["user_id", "fact_id"], ["facts.user_id", "facts.id"]),
    )
    resume_version_id: Mapped[str] = mapped_column(String(36))
    fact_id: Mapped[str] = mapped_column(String(36))
    statement_path: Mapped[str] = mapped_column(String(255))
    statement_text: Mapped[str] = mapped_column(Text)


class Application(Owned, Base):
    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("user_id", "id"),
        UniqueConstraint("user_id", "job_id", "attempt_no"),
        ForeignKeyConstraint(["user_id", "job_id"], ["jobs.user_id", "jobs.id"]),
        ForeignKeyConstraint(
            ["user_id", "resume_version_id"], ["resume_versions.user_id", "resume_versions.id"]
        ),
        CheckConstraint("attempt_no >= 1", name="positive_attempt"),
        CheckConstraint(
            "status IN ('pending','applied','hr_chat','interview_1','interview_2','offer','rejected','withdrawn')",
            name="status",
        ),
    )
    job_id: Mapped[str] = mapped_column(String(36))
    resume_version_id: Mapped[str | None] = mapped_column(String(36))
    attempt_no: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    applied_at: Mapped[date | None] = mapped_column(Date)
    hr_name: Mapped[str] = mapped_column(String(100), default="")
    hr_contact: Mapped[str] = mapped_column(String(255), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ApplicationEvent(Owned, Base):
    __tablename__ = "application_events"
    __table_args__ = (
        UniqueConstraint("user_id", "id"),
        UniqueConstraint("application_id", "sequence"),
        ForeignKeyConstraint(
            ["user_id", "application_id"], ["applications.user_id", "applications.id"]
        ),
    )
    application_id: Mapped[str] = mapped_column(String(36))
    sequence: Mapped[int] = mapped_column(Integer)
    from_status: Mapped[str | None] = mapped_column(String(30))
    to_status: Mapped[str] = mapped_column(String(30))
    notes: Mapped[str] = mapped_column(Text, default="")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Task(Owned, Base):
    __tablename__ = "tasks"
    __table_args__ = (
        UniqueConstraint("user_id", "id"),
        UniqueConstraint("user_id", "idempotency_key"),
        CheckConstraint(
            "status IN ('queued','running','retry','succeeded','failed','cancelled')", name="status"
        ),
        CheckConstraint("attempts >= 0 AND max_attempts >= 1", name="attempts"),
        Index("ix_tasks_dispatch", "status", "scheduled_at", "lease_expires_at"),
    )
    kind: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(30), default="queued")
    input_json: Mapped[dict] = mapped_column(JSON_VALUE, default=dict)
    output_json: Mapped[dict] = mapped_column(JSON_VALUE, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    idempotency_key: Mapped[str | None] = mapped_column(String(255))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claimed_by: Mapped[str | None] = mapped_column(String(200))


class AIRun(Owned, Base):
    __tablename__ = "ai_runs"
    __table_args__ = (
        UniqueConstraint("user_id", "id"),
        ForeignKeyConstraint(["user_id", "task_id"], ["tasks.user_id", "tasks.id"]),
        Index("ix_ai_runs_user_kind", "user_id", "kind", "created_at"),
    )
    task_id: Mapped[str | None] = mapped_column(String(36))
    kind: Mapped[str] = mapped_column(String(60))
    provider: Mapped[str] = mapped_column(String(50), default="openai")
    model: Mapped[str] = mapped_column(String(100), default="")
    prompt_version: Mapped[str] = mapped_column(String(100), default="v1")
    input_json: Mapped[dict] = mapped_column(JSON_VALUE, default=dict)
    output_json: Mapped[dict] = mapped_column(JSON_VALUE, default=dict)
    status: Mapped[str] = mapped_column(String(30), default="running")
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    request_id: Mapped[str | None] = mapped_column(String(255))
    error: Mapped[str | None] = mapped_column(Text)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MatchReport(Owned, Base):
    __tablename__ = "match_reports"
    __table_args__ = (
        UniqueConstraint("user_id", "id"),
        ForeignKeyConstraint(
            ["user_id", "job_id", "job_version_id"],
            ["job_versions.user_id", "job_versions.job_id", "job_versions.id"],
        ),
        ForeignKeyConstraint(
            ["user_id", "resume_version_id"], ["resume_versions.user_id", "resume_versions.id"]
        ),
        ForeignKeyConstraint(["user_id", "ai_run_id"], ["ai_runs.user_id", "ai_runs.id"]),
        CheckConstraint("score IS NULL OR (score >= 0 AND score <= 100)", name="score"),
    )
    job_id: Mapped[str] = mapped_column(String(36))
    job_version_id: Mapped[str] = mapped_column(String(36))
    resume_version_id: Mapped[str | None] = mapped_column(String(36))
    ai_run_id: Mapped[str | None] = mapped_column(String(36))
    score: Mapped[int | None] = mapped_column(Integer)
    requirements_json: Mapped[list] = mapped_column(JSON_VALUE, default=list)
    snapshot_json: Mapped[dict] = mapped_column(JSON_VALUE, default=dict)
    scoring_version: Mapped[str] = mapped_column(String(60), default="evidence-v1")


class Policy(Owned, Base):
    __tablename__ = "policies"
    __table_args__ = (
        UniqueConstraint("user_id", "id"),
        CheckConstraint("daily_target >= 1 AND daily_target <= 1000", name="daily_target"),
        CheckConstraint(
            "max_attempts_per_day >= 0 AND max_attempts_per_day <= 1000", name="daily_attempts"
        ),
    )
    name: Mapped[str] = mapped_column(String(200))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    daily_target: Mapped[int] = mapped_column(Integer, default=1000)
    max_attempts_per_day: Mapped[int] = mapped_column(Integer, default=1000)
    auto_submit: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_approve_grounded: Mapped[bool] = mapped_column(Boolean, default=False)
    schedule_time: Mapped[str] = mapped_column(String(5), default="09:00")
    timezone: Mapped[str] = mapped_column(String(100), default="Asia/Shanghai")
    filters_json: Mapped[dict] = mapped_column(JSON_VALUE, default=dict)
    channels_json: Mapped[list] = mapped_column(JSON_VALUE, default=list)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Batch(Owned, Base):
    __tablename__ = "batches"
    __table_args__ = (
        UniqueConstraint("user_id", "id"),
        UniqueConstraint("policy_id", "run_date"),
        ForeignKeyConstraint(["user_id", "policy_id"], ["policies.user_id", "policies.id"]),
        CheckConstraint(
            "status IN ('queued','running','paused','completed','failed')", name="status"
        ),
        CheckConstraint("target_count >= 1 AND target_count <= 1000", name="target_count"),
        CheckConstraint(
            "prepared_count >= 0 AND attempted_count >= 0 AND confirmed_count >= 0",
            name="nonnegative_counters",
        ),
    )
    policy_id: Mapped[str] = mapped_column(String(36))
    run_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30), default="queued")
    target_count: Mapped[int] = mapped_column(Integer, default=1000)
    prepared_count: Mapped[int] = mapped_column(Integer, default=0)
    attempted_count: Mapped[int] = mapped_column(Integer, default=0)
    confirmed_count: Mapped[int] = mapped_column(Integer, default=0)
    filters_snapshot: Mapped[dict] = mapped_column(JSON_VALUE, default=dict)
    channels_snapshot: Mapped[list] = mapped_column(JSON_VALUE, default=list)
    policy_snapshot: Mapped[dict] = mapped_column(JSON_VALUE, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BatchItem(Owned, Base):
    __tablename__ = "batch_items"
    __table_args__ = (
        UniqueConstraint("user_id", "id"),
        UniqueConstraint("batch_id", "job_id"),
        ForeignKeyConstraint(["user_id", "batch_id"], ["batches.user_id", "batches.id"]),
        ForeignKeyConstraint(
            ["user_id", "job_id", "job_version_id"],
            ["job_versions.user_id", "job_versions.job_id", "job_versions.id"],
        ),
        ForeignKeyConstraint(
            ["user_id", "resume_version_id"], ["resume_versions.user_id", "resume_versions.id"]
        ),
        ForeignKeyConstraint(["user_id", "task_id"], ["tasks.user_id", "tasks.id"]),
        Index("ix_batch_items_dispatch", "batch_id", "status"),
    )
    batch_id: Mapped[str] = mapped_column(String(36))
    job_id: Mapped[str] = mapped_column(String(36))
    job_version_id: Mapped[str] = mapped_column(String(36))
    resume_version_id: Mapped[str | None] = mapped_column(String(36))
    task_id: Mapped[str | None] = mapped_column(String(36))
    channel: Mapped[str] = mapped_column(String(60), default="prepare_open")
    capability: Mapped[str] = mapped_column(String(60), default="prepare_open")
    status: Mapped[str] = mapped_column(String(40), default="queued")
    prepared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    artifact_path: Mapped[str | None] = mapped_column(Text)
    artifact_sha256: Mapped[str | None] = mapped_column(String(64))
    receipt_json: Mapped[dict] = mapped_column(JSON_VALUE, default=dict)
    error: Mapped[str | None] = mapped_column(Text)


class MessageDraft(Owned, Base):
    __tablename__ = "message_drafts"
    __table_args__ = (
        UniqueConstraint("user_id", "id"),
        ForeignKeyConstraint(["user_id", "job_id"], ["jobs.user_id", "jobs.id"]),
        ForeignKeyConstraint(["user_id", "ai_run_id"], ["ai_runs.user_id", "ai_runs.id"]),
    )
    job_id: Mapped[str] = mapped_column(String(36))
    ai_run_id: Mapped[str | None] = mapped_column(String(36))
    channel: Mapped[str] = mapped_column(String(60))
    purpose: Mapped[str] = mapped_column(String(60), default="opening")
    language: Mapped[str] = mapped_column(String(10), default="zh")
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="draft")
    fact_ids_json: Mapped[list] = mapped_column(JSON_VALUE, default=list)


class CoachingSession(Owned, Base):
    __tablename__ = "coaching_sessions"
    __table_args__ = (
        UniqueConstraint("user_id", "id"),
        ForeignKeyConstraint(["user_id", "job_id"], ["jobs.user_id", "jobs.id"]),
        ForeignKeyConstraint(["user_id", "ai_run_id"], ["ai_runs.user_id", "ai_runs.id"]),
    )
    job_id: Mapped[str | None] = mapped_column(String(36))
    ai_run_id: Mapped[str | None] = mapped_column(String(36))
    kind: Mapped[str] = mapped_column(String(40), default="interview")
    title: Mapped[str] = mapped_column(String(255), default="")
    messages_json: Mapped[list] = mapped_column(JSON_VALUE, default=list)
    feedback_json: Mapped[dict] = mapped_column(JSON_VALUE, default=dict)


# A fact row is one immutable revision, not an editable logical fact.
FactRevision = Fact
