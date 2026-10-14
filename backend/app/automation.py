"""Database-backed scheduling and task leases. PostgreSQL supports many workers.

SQLite intentionally supports a single local worker. Queue creation and business
records share one database transaction; there is no queue dual-write gap.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.channels import CHANNELS
from app.config import settings
from app.models import Application, Batch, BatchItem, Job, JobVersion, Policy, Task, utcnow


def enqueue(db: Session, user_id: str, kind: str, inputs: dict, key: str | None = None,
            max_attempts: int = 3) -> Task:
    if key:
        existing = db.scalar(select(Task).where(Task.user_id == user_id, Task.idempotency_key == key))
        if existing:
            return existing
    task = Task(user_id=user_id, kind=kind, input_json=inputs,
                idempotency_key=key, max_attempts=max_attempts)
    try:
        with db.begin_nested():
            db.add(task)
            db.flush()
    except IntegrityError:
        if not key:
            raise
        return db.scalar(select(Task).where(Task.user_id == user_id, Task.idempotency_key == key))
    return task


def policy_snapshot(policy: Policy) -> dict:
    return {key: getattr(policy, key) for key in (
        "id", "name", "daily_target", "max_attempts_per_day", "auto_submit",
        "auto_approve_grounded", "filters_json", "channels_json", "schedule_time", "timezone",
    )}


def create_batch(db: Session, policy: Policy, now: datetime | None = None) -> Batch:
    moment = now or utcnow()
    local_date = moment.astimezone(ZoneInfo(policy.timezone)).date()
    existing = db.scalar(select(Batch).where(Batch.policy_id == policy.id, Batch.run_date == local_date))
    if existing:
        return existing
    filters = policy.filters_json or {}
    jobs = db.scalars(select(Job).where(Job.user_id == policy.user_id, Job.status == "active",
                                       Job.jd_complete.is_(True))
                      .order_by(Job.created_at.desc())).all()
    already_applied = set(db.scalars(select(Application.job_id).where(
        Application.user_id == policy.user_id, Application.status != "pending",
    )))
    previous_items = set(db.scalars(select(BatchItem.job_id).where(
        BatchItem.user_id == policy.user_id,
        BatchItem.status.in_(["mail_accepted", "application_received", "unknown"]),
    )))
    selected = []
    for job in jobs:
        combined = f"{job.company} {job.title} {job.jd_text}".lower()
        if job.id in already_applied or job.id in previous_items:
            continue
        if job.deadline and job.deadline < local_date:
            continue
        if filters.get("roles") and not any(str(x).lower() in job.title.lower() for x in filters["roles"]):
            continue
        if filters.get("locations") and not any(str(x).lower() in job.location.lower() for x in filters["locations"]):
            continue
        if any(str(x).lower() in combined for x in filters.get("exclude_keywords", [])):
            continue
        if not job.jd_text.strip():
            continue
        selected.append(job)
        if len(selected) >= policy.daily_target:
            break
    batch = Batch(
        user_id=policy.user_id, policy_id=policy.id, run_date=local_date,
        target_count=policy.daily_target, filters_snapshot=dict(filters),
        channels_snapshot=list(policy.channels_json), policy_snapshot=policy_snapshot(policy),
        status="queued" if selected else "completed",
        error=None if selected else "没有符合条件且尚未投递的有效岗位",
    )
    try:
        with db.begin_nested():
            db.add(batch)
            db.flush()
    except IntegrityError:
        return db.scalar(select(Batch).where(Batch.policy_id == policy.id, Batch.run_date == local_date))
    channels = policy.channels_json or ["prepare_open"]
    for job in selected:
        version = db.scalar(select(JobVersion).where(JobVersion.user_id == policy.user_id,
                                                    JobVersion.job_id == job.id,
                                                    JobVersion.version_number == job.version_number))
        if version is None:
            continue
        channel = channels[0]
        if job.source_url and "zhipin.com" in job.source_url and "boss" in channels:
            channel = "boss"
        elif job.source_url and "weixin" in job.source_url and "wechat" in channels:
            channel = "wechat"
        elif "email" in channels and "@" in version.jd_text:
            channel = "email"
        if channel not in CHANNELS:
            channel = "prepare_open"
        item = BatchItem(user_id=policy.user_id, batch_id=batch.id, job_id=job.id,
                         job_version_id=version.id, channel=channel,
                         capability="smtp" if channel == "email" else "prepare_open")
        db.add(item)
        db.flush()
        task = enqueue(db, policy.user_id, "prepare_item", {"item_id": item.id},
                       key=f"prepare:{item.id}")
        item.task_id = task.id
    policy.last_run_at = moment
    db.flush()
    return batch


def schedule_due(db: Session, now: datetime | None = None) -> list[str]:
    moment = now or utcnow()
    batches = []
    for policy in db.scalars(select(Policy).where(Policy.enabled.is_(True))):
        local = moment.astimezone(ZoneInfo(policy.timezone))
        hour, minute = map(int, policy.schedule_time.split(":"))
        if (local.hour, local.minute) >= (hour, minute):
            existing = db.scalar(select(Batch.id).where(Batch.policy_id == policy.id,
                                                        Batch.run_date == local.date()))
            if not existing and policy.filters_json.get("sync_sources"):
                task = enqueue(db, policy.user_id, "policy_sync_and_run", {"policy_id": policy.id},
                               key=f"daily-source:{policy.id}:{local.date()}")
                batches.append(task.id)
            else:
                batches.append(create_batch(db, policy, moment).id)
    db.commit()
    return batches


def claim_task(db: Session, worker_id: str, now: datetime | None = None) -> Task | None:
    moment = now or utcnow()
    expired = db.scalars(select(Task).where(Task.status == "running",
                                           Task.lease_expires_at < moment).with_for_update(skip_locked=True)).all()
    for task in expired:
        # External submission may already have happened; never replay a lost send lease.
        if task.kind == "submit_item":
            task.status, task.error, task.finished_at = "failed", "提交租约丢失：需要核实结果，禁止自动重试", moment
            item = db.get(BatchItem, task.input_json.get("item_id"))
            if item and item.status == "sending":
                item.status = "unknown"
                item.receipt_json = {"kind": "unknown", "detail": task.error}
        elif task.attempts >= task.max_attempts:
            task.status, task.error, task.finished_at = "failed", "任务租约过期，达到最大尝试次数", moment
        else:
            task.status, task.scheduled_at = "retry", moment
        task.claimed_by, task.lease_expires_at = None, None
    db.flush()
    candidate = db.scalar(select(Task).where(
        Task.status.in_(["queued", "retry"]), Task.scheduled_at <= moment,
        Task.attempts < Task.max_attempts,
    ).order_by(Task.scheduled_at, Task.created_at).with_for_update(skip_locked=True).limit(1))
    if candidate is None:
        db.commit()
        return None
    candidate.status, candidate.claimed_by = "running", f"{worker_id}:{uuid4().hex}"
    candidate.attempts += 1
    candidate.started_at = candidate.started_at or moment
    candidate.heartbeat_at = moment
    candidate.lease_expires_at = moment + timedelta(seconds=settings.task_lease_seconds)
    db.commit()
    return candidate


def finish_task(db: Session, task_id: str, worker_id: str, result: dict | None = None,
                error: str | None = None, retryable: bool = False):
    task = db.scalar(select(Task).where(Task.id == task_id).with_for_update())
    expires = task.lease_expires_at if task else None
    moment = utcnow()
    if expires is not None and expires.tzinfo is None:
        expires = expires.replace(tzinfo=moment.tzinfo)
    if (not task or task.status != "running" or task.claimed_by != worker_id
            or not expires or expires < moment):
        db.rollback()
        raise RuntimeError("Worker 已失去该任务的租约")
    if error and retryable and task.kind != "submit_item" and task.attempts < task.max_attempts:
        task.status = "retry"
        task.scheduled_at = utcnow() + timedelta(seconds=min(60, 2 ** task.attempts * 5))
    else:
        task.status = "failed" if error else "succeeded"
        task.finished_at = utcnow()
    task.output_json, task.error = result or {}, error
    task.claimed_by, task.lease_expires_at = None, None
    db.commit()


def refresh_batch(db: Session, batch_id: str):
    db.flush()
    batch = db.scalar(select(Batch).where(Batch.id == batch_id).with_for_update()
                      .execution_options(populate_existing=True))
    if not batch:
        return
    items = db.scalars(select(BatchItem).where(BatchItem.batch_id == batch_id)
                       .execution_options(populate_existing=True)).all()
    batch.prepared_count = sum(item.prepared_at is not None for item in items)
    batch.attempted_count = sum(item.attempted_at is not None for item in items)
    batch.confirmed_count = sum(item.receipt_json.get("kind") == "application_received" for item in items)
    if batch.status != "paused":
        outstanding = any(item.status in {"queued", "preparing", "submit_queued", "sending"} for item in items)
        batch.status = "running" if outstanding else "completed"
        if not outstanding:
            batch.finished_at = utcnow()
    db.flush()


def attempt_count_today(db: Session, user_id: str) -> int:
    local = utcnow().astimezone(ZoneInfo("Asia/Shanghai"))
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return db.scalar(select(func.count()).select_from(BatchItem).where(
        BatchItem.user_id == user_id, BatchItem.attempted_at >= start,
    )) or 0
