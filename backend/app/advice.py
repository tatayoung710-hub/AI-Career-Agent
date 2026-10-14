"""Small, explainable advice rules; no invented hiring intentions."""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Application, Fact, Job, ResumeVersion, utcnow


def get_advice(db: Session, user_id: str) -> list[dict]:
    advice = []
    confirmed = db.scalar(select(Fact.id).where(Fact.user_id == user_id, Fact.confirmed.is_(True)).limit(1))
    if not confirmed:
        advice.append({"id": "confirm_facts", "kind": "profile", "title": "先确认真实经历",
                       "reason": "定制简历需要用户确认的事实来源。", "action": "facts"})
    cutoff = (utcnow() - timedelta(days=7)).date()
    for application in db.scalars(select(Application).where(Application.user_id == user_id)):
        job = db.get(Job, application.job_id)
        label = f"{job.company} · {job.title}" if job else "申请"
        if application.status == "applied" and application.applied_at and application.applied_at <= cutoff:
            advice.append({"id": f"followup:{application.id}", "kind": "follow_up", "title": f"考虑跟进：{label}",
                           "reason": "记录的投递日期已超过 7 天；结合实际沟通时间决定是否联系。",
                           "job_id": application.job_id, "action": "communications"})
        if application.status in {"interview_1", "interview_2"}:
            advice.append({"id": f"interview:{application.id}", "kind": "interview", "title": f"准备面试：{label}",
                           "reason": "围绕 JD 核心要求，为已确认经历准备职责、方法、结果和追问。",
                           "job_id": application.job_id, "action": "coaching"})
        if not application.resume_version_id:
            advice.append({"id": f"resume:{application.id}", "kind": "resume", "title": f"绑定简历版本：{label}",
                           "reason": "保存实际使用的简历版本，便于面试与历史追溯。", "action": "resumes"})
    for version in db.scalars(select(ResumeVersion).where(
        ResumeVersion.user_id == user_id, ResumeVersion.evidence_status == "validated",
        ResumeVersion.approved_at.is_(None),
    ).limit(10)):
        advice.append({"id": f"approve:{version.id}", "kind": "resume", "title": "审阅岗位专属简历",
                       "reason": "事实检查已通过；请审阅最终表述后批准导出。", "action": "resumes"})
    return advice[:50]
