"""Run independently: python -m app.worker [--once]. No API-process scheduler."""

import argparse
import hashlib
import logging
import os
import socket
import threading
import time
from datetime import timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, update

from app.automation import (
    attempt_count_today, claim_task, create_batch, enqueue, finish_task, refresh_batch, schedule_due,
)
from app.channels import CHANNELS
from app.channels.sources import sync_source
from app.config import settings
from app.db import SessionLocal
from app.models import (
    Application, ApplicationEvent, Batch, BatchItem, Fact, Policy, ResumeVersion,
    Source, Task, User, utcnow,
)

logger = logging.getLogger(__name__)


def check_lease(db, task_id: str, owner: str):
    task = db.scalar(select(Task).where(Task.id == task_id).with_for_update())
    moment = utcnow()
    expires = task.lease_expires_at if task else None
    if expires is not None and expires.tzinfo is None:
        expires = expires.replace(tzinfo=moment.tzinfo)
    if not task or task.status != "running" or task.claimed_by != owner or not expires or expires < moment:
        raise RuntimeError("Worker 失去租约，不能写入任务结果")
    return task


class LeaseHeartbeat:
    def __init__(self, task_id: str, owner: str):
        self.task_id, self.owner = task_id, owner
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)

    def run(self):
        while not self.stop.wait(max(5, settings.task_lease_seconds / 3)):
            try:
                with SessionLocal() as db:
                    now = utcnow()
                    db.execute(update(Task).where(Task.id == self.task_id, Task.claimed_by == self.owner,
                                                  Task.status == "running").values(
                        heartbeat_at=now, lease_expires_at=now + timedelta(seconds=settings.task_lease_seconds)))
                    db.commit()
            except Exception:
                logger.exception("Task heartbeat failed")

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_args):
        self.stop.set()
        self.thread.join(timeout=5)


def prepare_item(db, user_id: str, item_id: str, task_id: str, owner: str) -> dict:
    item = db.scalar(select(BatchItem).where(BatchItem.id == item_id, BatchItem.user_id == user_id))
    if not item:
        raise ValueError("批次岗位不存在")
    batch = db.get(Batch, item.batch_id)
    if batch.status == "paused":
        item.status = "paused"
        db.commit()
        return {"kind": "paused", "item_id": item.id}
    if item.prepared_at:
        return {"kind": "prepared", "item_id": item.id, "resume_version_id": item.resume_version_id}
    item.status, batch.status = "preparing", "running"
    db.commit()
    from app.ai.service import match_job, tailor_resume
    filters = batch.filters_snapshot
    report = match_job(db, user_id, item.job_id, job_version_id=item.job_version_id, task_id=task_id)
    if report.score is None or report.score < filters.get("min_score", 0) or any(
        requirement.get("hard_requirement") and requirement.get("support") != "supported"
        for requirement in report.requirements_json
    ):
        check_lease(db, task_id, owner)
        item.status, item.error = "skipped", "匹配程度不足或硬性条件未满足/待核实，不能自动投递"
        refresh_batch(db, item.batch_id)
        db.commit()
        return {"kind": "skipped", "item_id": item.id}
    version = tailor_resume(db, user_id, item.job_id, language=filters.get("language", "zh"),
                            style=filters.get("style", "professional"),
                            job_version_id=item.job_version_id, task_id=task_id,
                            before_save=lambda: check_lease(db, task_id, owner))
    check_lease(db, task_id, owner)
    db.refresh(batch)
    policy = db.get(Policy, batch.policy_id)
    item.resume_version_id = version.id
    if version.evidence_status != "validated":
        item.status, item.error = "awaiting_approval", "简历事实检查未通过，不能自动批准或提交"
    else:
        if batch.policy_snapshot.get("auto_approve_grounded") and policy.auto_approve_grounded:
            version.approved_at = utcnow()
            version.approval_source = "policy"
            version.approval_policy_snapshot = batch.policy_snapshot
        item.prepared_at = utcnow()
        item.status = "prepared" if version.approved_at else "awaiting_approval"
        item.receipt_json = {"kind": "prepared", "entry_url": version.job_snapshot.get("source_url", ""),
                             "detail": CHANNELS[item.channel].explanation}
        if version.approved_at:
            from app.core_routes import export_resume_version
            path = export_resume_version(db, user_id, version.id, "pdf")
            item.artifact_path = str(path)
            item.artifact_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        if (version.approved_at and batch.status != "paused" and policy.auto_submit
                and batch.policy_snapshot.get("auto_submit") and item.channel == "email"
                and item.channel in policy.channels_json):
            task = enqueue(db, user_id, "submit_item", {"item_id": item.id}, key=f"submit:{item.id}", max_attempts=1)
            item.task_id, item.status = task.id, "submit_queued"
    refresh_batch(db, item.batch_id)
    db.commit()
    return {"kind": item.status, "item_id": item.id, "resume_version_id": version.id}


def submit_item(db, user_id: str, item_id: str, task_id: str, owner: str) -> dict:
    item = db.scalar(select(BatchItem).where(BatchItem.id == item_id, BatchItem.user_id == user_id))
    if not item:
        raise ValueError("批次岗位不存在")
    batch = db.scalar(select(Batch).where(Batch.id == item.batch_id).with_for_update())
    policy = db.get(Policy, batch.policy_id)
    if batch.status == "paused" or not policy.auto_submit or item.channel not in policy.channels_json:
        item.status, item.error = "blocked", "批次暂停或发送授权已撤销"
        db.commit()
        return {"kind": "blocked"}
    if item.status in {"unknown", "mail_accepted", "application_received", "sending"} or item.attempted_at:
        return {"kind": item.status, "detail": "已尝试或结果不确定，禁止自动重发"}
    if item.channel != "email":
        raise ValueError("当前渠道没有获准提交连接器")
    if not settings.email_submit_enabled:
        item.status, item.error = "blocked", "服务器未启用 SMTP 发送"
        db.commit()
        return {"kind": "blocked"}
    if attempt_count_today(db, user_id) >= min(1000, policy.max_attempts_per_day):
        item.status, item.error = "blocked", "达到当日尝试次数上限"
        db.commit()
        return {"kind": "blocked"}
    version = db.scalar(select(ResumeVersion).where(ResumeVersion.id == item.resume_version_id,
                                                   ResumeVersion.user_id == user_id))
    if not version or not version.approved_at or version.evidence_status != "validated":
        raise ValueError("提交版本未通过事实检查或审批")
    from app.ai.evidence import validate_resume_evidence
    facts = db.scalars(select(Fact).where(Fact.user_id == user_id)).all()
    check = validate_resume_evidence(version.content, facts)
    if not check.valid:
        raise ValueError("发送前事实检查失败：" + "; ".join(check.errors))
    from app.core_routes import export_resume_version
    path = export_resume_version(db, user_id, version.id, "pdf")
    from app.ai.service import draft_message
    draft = draft_message(db, user_id, item.job_id, "email", "application", task_id=task_id,
                          job_version_id=item.job_version_id)
    check_lease(db, task_id, owner)
    db.refresh(policy)
    db.refresh(batch)
    if batch.status == "paused" or not policy.auto_submit or item.channel not in policy.channels_json:
        raise ValueError("发送授权已撤销")
    db.scalar(select(User).where(User.id == user_id).with_for_update())
    if attempt_count_today(db, user_id) >= min(1000, policy.max_attempts_per_day):
        item.status, item.error = "blocked", "达到当日尝试次数上限"
        db.commit()
        return {"kind": "blocked"}
    other_attempt = db.scalar(select(BatchItem.id).where(
        BatchItem.user_id == user_id, BatchItem.job_id == item.job_id,
        BatchItem.id != item.id, BatchItem.attempted_at.is_not(None),
    ).limit(1))
    applied = db.scalar(select(Application.id).where(
        Application.user_id == user_id, Application.job_id == item.job_id,
        Application.status != "pending",
    ).limit(1))
    if other_attempt or applied:
        item.status, item.error = "blocked", "该岗位已有发送尝试或投递记录，防止跨策略重复投递"
        db.commit()
        return {"kind": "blocked"}
    # Commit the externally-visible attempt before SMTP. A crash now becomes unknown.
    item.status, item.attempted_at = "sending", utcnow()
    db.commit()
    from app.channels.email import send_recruiting_email
    receipt = send_recruiting_email(version.job_snapshot.get("jd_text", ""),
                                    f"岗位申请 · {version.job_snapshot.get('title', '')}", draft.content, path)
    check_lease(db, task_id, owner)
    item.status, item.receipt_json = receipt["kind"], receipt
    if receipt["kind"] == "mail_accepted":
        application = db.scalar(select(Application).where(
            Application.user_id == user_id, Application.job_id == item.job_id,
            Application.status == "pending",
        ).order_by(Application.attempt_no.desc()).with_for_update().limit(1))
        if application is None:
            attempt = db.scalar(select(func.max(Application.attempt_no)).where(
                Application.user_id == user_id, Application.job_id == item.job_id,
            )) or 0
            application = Application(user_id=user_id, job_id=item.job_id, attempt_no=attempt + 1)
            db.add(application)
            db.flush()
        previous = application.status
        application.status = "applied"
        application.version += 1
        application.resume_version_id = version.id
        application.applied_at = utcnow().astimezone(ZoneInfo("Asia/Shanghai")).date()
        application.hr_contact = receipt["recipient"]
        application.notes = "招聘邮件已被 SMTP 服务器受理；尚未确认 HR 收到或招聘系统受理。"
        sequence = db.scalar(select(func.max(ApplicationEvent.sequence)).where(
            ApplicationEvent.application_id == application.id,
        )) or 0
        db.add(ApplicationEvent(user_id=user_id, application_id=application.id,
                                sequence=sequence + 1, from_status=previous, to_status="applied",
                                notes=f"SMTP mail_accepted · {receipt['message_id']} · 非申请受理回执"))
    refresh_batch(db, item.batch_id)
    db.commit()
    return receipt


def execute_task(task_id: str, owner: str):
    with SessionLocal() as db:
        task = check_lease(db, task_id, owner)
        kind, user_id, inputs = task.kind, task.user_id, dict(task.input_json)
        db.commit()
        if kind == "policy_sync_and_run":
            policy = db.scalar(select(Policy).where(Policy.id == inputs["policy_id"], Policy.user_id == user_id))
            if not policy or not policy.enabled:
                result = {"kind": "blocked", "detail": "每日策略已关闭"}
            else:
                source_results = []
                sources = db.scalars(select(Source).where(Source.user_id == user_id,
                                                          Source.archived.is_(False))).all()
                for source in sources:
                    try:
                        source_results.append(sync_source(db, user_id, source.id))
                        check_lease(db, task_id, owner)
                        db.commit()
                    except Exception as exc:
                        db.rollback()
                        source_results.append({"source_id": source.id, "error": str(exc)[:300]})
                check_lease(db, task_id, owner)
                batch = create_batch(db, policy)
                db.commit()
                result = {"batch_id": batch.id, "source_results": source_results}
        elif kind == "source_sync":
            result = sync_source(db, user_id, inputs["source_id"])
            check_lease(db, task_id, owner)
            db.commit()
        elif kind == "prepare_item":
            result = prepare_item(db, user_id, inputs["item_id"], task_id, owner)
        elif kind == "submit_item":
            result = submit_item(db, user_id, inputs["item_id"], task_id, owner)
        else:
            raise ValueError(f"未注册任务类型：{kind}")
        finish_task(db, task_id, owner, result)


def run_once(worker_id: str) -> bool:
    with SessionLocal() as db:
        schedule_due(db)
        task = claim_task(db, worker_id)
        if not task:
            return False
        task_id, owner = task.id, task.claimed_by
    try:
        with LeaseHeartbeat(task_id, owner):
            execute_task(task_id, owner)
    except Exception as exc:
        logger.warning("Task failed: %s", type(exc).__name__)
        with SessionLocal() as db:
            task = db.get(Task, task_id)
            if not task or task.claimed_by != owner or task.status != "running":
                return True
            try:
                check_lease(db, task_id, owner)
            except RuntimeError:
                db.rollback()
                return True
            item_id = task.input_json.get("item_id")
            item = db.get(BatchItem, item_id) if item_id else None
            if item:
                if item.status == "sending":
                    item.status = "unknown"
                    item.receipt_json = {"kind": "unknown", "detail": "发送结果未确认，禁止自动重试"}
                else:
                    item.status = "failed"
                item.error = str(exc)[:2000]
                refresh_batch(db, item.batch_id)
            finish_task(db, task_id, owner, error=str(exc)[:2000], retryable=False)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    worker_id = f"{socket.gethostname()}:{os.getpid()}:{uuid4().hex[:12]}"
    if args.once:
        run_once(worker_id)
        return
    logger.info("Durable worker started; production multi-worker requires PostgreSQL")
    try:
        while True:
            if not run_once(worker_id):
                time.sleep(settings.worker_poll_seconds)
    except KeyboardInterrupt:
        logger.info("Worker stopped")


if __name__ == "__main__":
    main()
