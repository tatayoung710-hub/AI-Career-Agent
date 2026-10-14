"""Daily policies, batches and transparent execution progress."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.advice import get_advice
from app.auth import get_current_user
from app.automation import create_batch, enqueue, refresh_batch
from app.channels import CHANNELS, channel_list
from app.db import get_db
from app.models import Batch, BatchItem, Policy, ResumeVersion, Task, User, utcnow

router = APIRouter(tags=["Automation"])


def serialize(obj) -> dict:
    return {column.key: getattr(obj, column.key) for column in inspect(type(obj)).columns}


class PolicyFilters(BaseModel):
    roles: list[str] = Field(default_factory=list, max_length=50)
    locations: list[str] = Field(default_factory=list, max_length=50)
    exclude_keywords: list[str] = Field(default_factory=list, max_length=50)
    min_score: int = Field(default=0, ge=0, le=100)
    language: Literal["zh", "en"] = "zh"
    style: str = Field(default="professional", max_length=50)
    max_ai_calls: int = Field(default=4000, ge=1, le=10000)
    sync_sources: bool = False


class PolicyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    enabled: bool = False
    daily_target: int = Field(default=1000, ge=1, le=1000)
    max_attempts_per_day: int = Field(default=1000, ge=0, le=1000)
    auto_submit: bool = False
    auto_approve_grounded: bool = False
    schedule_time: str = Field(default="09:00", pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    timezone: Literal["Asia/Shanghai"] = "Asia/Shanghai"
    filters_json: PolicyFilters = Field(default_factory=PolicyFilters)
    channels_json: list[str] = Field(default_factory=lambda: ["prepare_open"], min_length=1, max_length=10)

    @field_validator("channels_json")
    @classmethod
    def known_channels(cls, values):
        if any(value not in CHANNELS for value in values):
            raise ValueError("包含未实现的渠道")
        return list(dict.fromkeys(values))


class PolicyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    enabled: bool | None = None
    daily_target: int | None = Field(default=None, ge=1, le=1000)
    max_attempts_per_day: int | None = Field(default=None, ge=0, le=1000)
    auto_submit: bool | None = None
    auto_approve_grounded: bool | None = None
    schedule_time: str | None = Field(default=None, pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    timezone: Literal["Asia/Shanghai"] | None = None
    filters_json: PolicyFilters | None = None
    channels_json: list[str] | None = Field(default=None, min_length=1, max_length=10)

    @field_validator("channels_json")
    @classmethod
    def known_channels(cls, values):
        if values is not None and any(value not in CHANNELS for value in values):
            raise ValueError("包含未实现的渠道")
        return list(dict.fromkeys(values)) if values is not None else values


class RunRequest(BaseModel):
    policy_id: str


@router.get("/channels")
def channels(user: User = Depends(get_current_user)):
    return channel_list()


@router.get("/automation/policies")
def list_policies(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return [serialize(value) for value in db.scalars(select(Policy).where(Policy.user_id == user.id))]


@router.post("/automation/policies", status_code=201)
def add_policy(payload: PolicyCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    policy = Policy(user_id=user.id, **payload.model_dump())
    db.add(policy)
    db.commit()
    return serialize(policy)


@router.patch("/automation/policies/{policy_id}")
def update_policy(policy_id: str, payload: PolicyUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    policy = db.scalar(select(Policy).where(Policy.id == policy_id, Policy.user_id == user.id))
    if not policy:
        raise HTTPException(404, "策略不存在")
    for key, value in payload.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(policy, key, value)
    db.commit()
    return serialize(policy)


@router.post("/automation/run", status_code=202)
def run_policy(payload: RunRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    policy = db.scalar(select(Policy).where(Policy.id == payload.policy_id, Policy.user_id == user.id))
    if not policy:
        raise HTTPException(404, "策略不存在")
    batch = create_batch(db, policy)
    db.commit()
    return serialize(batch)


@router.get("/automation/batches")
def list_batches(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return [serialize(value) for value in db.scalars(select(Batch).where(Batch.user_id == user.id)
                                                    .order_by(Batch.created_at.desc()).limit(100))]


def owned_batch(db: Session, user_id: str, batch_id: str) -> Batch:
    batch = db.scalar(select(Batch).where(Batch.id == batch_id, Batch.user_id == user_id))
    if not batch:
        raise HTTPException(404, "批次不存在")
    return batch


@router.get("/automation/batches/{batch_id}")
def batch_detail(batch_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    batch = owned_batch(db, user.id, batch_id)
    return {**serialize(batch), "items": [serialize(value) for value in db.scalars(
        select(BatchItem).where(BatchItem.user_id == user.id, BatchItem.batch_id == batch_id)
        .order_by(BatchItem.created_at).limit(1000))]}


@router.get("/automation/batches/{batch_id}/items")
def batch_items(batch_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    owned_batch(db, user.id, batch_id)
    return [serialize(value) for value in db.scalars(select(BatchItem).where(
        BatchItem.user_id == user.id, BatchItem.batch_id == batch_id).limit(1000))]


@router.post("/automation/batches/{batch_id}/pause")
def pause_batch(batch_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    batch = owned_batch(db, user.id, batch_id)
    batch.status = "paused"
    items = db.scalars(select(BatchItem).where(BatchItem.batch_id == batch.id)).all()
    for item in items:
        task = db.get(Task, item.task_id) if item.task_id else None
        if task and task.status in {"queued", "retry"}:
            task.status = "cancelled"
    db.commit()
    return serialize(batch)


@router.post("/automation/batches/{batch_id}/resume")
def resume_batch(batch_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    batch = owned_batch(db, user.id, batch_id)
    batch.status = "running"
    for item in db.scalars(select(BatchItem).where(BatchItem.batch_id == batch.id)):
        task = db.get(Task, item.task_id) if item.task_id else None
        if task and task.status == "cancelled" and item.status in {"queued", "submit_queued"}:
            task.status, task.scheduled_at = "queued", utcnow()
        elif task and task.status == "succeeded" and item.status == "paused":
            task.status, task.scheduled_at, task.attempts = "queued", utcnow(), 0
            item.status = "queued"
    refresh_batch(db, batch.id)
    db.commit()
    return serialize(batch)


@router.post("/automation/items/{item_id}/submit", status_code=202)
def submit_item(item_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = db.scalar(select(BatchItem).where(BatchItem.id == item_id, BatchItem.user_id == user.id))
    if not item:
        raise HTTPException(404, "批次岗位不存在")
    if not CHANNELS.get(item.channel, CHANNELS["prepare_open"]).can_submit:
        raise HTTPException(409, "当前渠道仅支持准备材料，请在原招聘入口完成投递")
    if item.status in {"sending", "unknown", "mail_accepted", "application_received"}:
        raise HTTPException(409, "已发起或结果待核实，禁止重复提交")
    batch = owned_batch(db, user.id, item.batch_id)
    policy = db.get(Policy, batch.policy_id)
    if batch.status == "paused" or not policy.auto_submit or item.channel not in policy.channels_json:
        raise HTTPException(409, "批次暂停或策略未授权此渠道发送")
    version = db.get(ResumeVersion, item.resume_version_id) if item.resume_version_id else None
    if not version or not version.approved_at or version.evidence_status != "validated":
        raise HTTPException(409, "简历尚未通过事实检查和审批")
    task = enqueue(db, user.id, "submit_item", {"item_id": item.id}, key=f"submit:{item.id}", max_attempts=1)
    if task.status in {"failed", "succeeded"}:
        raise HTTPException(409, "该提交任务已有结果，不能自动重发")
    item.status, item.task_id = "submit_queued", task.id
    batch.status = "running"
    db.commit()
    return serialize(task)


@router.get("/tasks")
def list_tasks(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return [serialize(value) for value in db.scalars(select(Task).where(Task.user_id == user.id)
                                                    .order_by(Task.created_at.desc()).limit(100))]


@router.get("/tasks/{task_id}")
def task_detail(task_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    task = db.scalar(select(Task).where(Task.id == task_id, Task.user_id == user.id))
    if not task:
        raise HTTPException(404, "任务不存在")
    return serialize(task)


@router.get("/advice")
def advice(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return get_advice(db, user.id)
