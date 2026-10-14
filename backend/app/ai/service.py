"""OpenAI Responses integration and evidence-grounded career workflows."""

import hashlib
import json
import threading
from typing import TypeVar

from fastapi import HTTPException
from openai import APIError, OpenAI
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.api_schemas import (
    ChatOutput,
    DraftOutput,
    JobExtraction,
    MatchOutput,
    ResumeAudit,
    ResumeOutput,
    ReviewOutput,
)
from app.ai.evidence import fact_snapshot, iter_claims, validate_resume_evidence
from app.config import settings
from app.models import (
    AIRun,
    CoachingSession,
    Fact,
    Job,
    JobVersion,
    MatchReport,
    MessageDraft,
    Profile,
    Resume,
    ResumeEvidence,
    ResumeVersion,
    utcnow,
)

T = TypeVar("T", bound=BaseModel)
_AI_LIMIT = threading.BoundedSemaphore(settings.ai_max_concurrency)


def _client() -> OpenAI:
    if not settings.openai_api_key:
        raise HTTPException(503, "AI 尚未配置：请在 backend/.env 设置 OPENAI_API_KEY 后重启服务")
    return OpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        timeout=settings.ai_timeout_seconds,
        max_retries=0,
    )


def _invoke(
    db: Session,
    user_id: str,
    kind: str,
    instructions: str,
    payload: dict,
    schema: type[T],
    *,
    task_id: str | None = None,
    max_output_tokens: int = 5000,
) -> tuple[T, AIRun]:
    client = _client()
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    run = AIRun(
        user_id=user_id,
        task_id=task_id,
        kind=kind,
        provider="openai",
        model=settings.openai_model,
        prompt_version=f"{kind}-v1",
        input_json={"sha256": hashlib.sha256(encoded.encode()).hexdigest(), "characters": len(encoded)},
        status="running",
    )
    db.add(run)
    db.commit()
    try:
        with _AI_LIMIT:
            response = client.responses.parse(
                model=settings.openai_model,
                instructions=instructions,
                input=encoded,
                text_format=schema,
                max_output_tokens=max_output_tokens,
                store=False,
            )
        parsed = response.output_parsed
        if parsed is None:
            raise ValueError("模型没有返回符合结构的结果")
        parsed = schema.model_validate(parsed)
        usage = response.usage
        run.status = "succeeded"
        run.output_json = parsed.model_dump(mode="json")
        run.input_tokens = getattr(usage, "input_tokens", None) if usage else None
        run.output_tokens = getattr(usage, "output_tokens", None) if usage else None
        run.request_id = getattr(response, "_request_id", None)
        run.finished_at = utcnow()
        db.commit()
        return parsed, run
    except Exception as exc:
        db.rollback()
        run = db.get(AIRun, run.id)
        if run:
            run.status = "failed"
            run.error = f"{type(exc).__name__}: {str(exc)[:1500]}"
            run.finished_at = utcnow()
            db.commit()
        if isinstance(exc, HTTPException):
            raise
        if isinstance(exc, APIError):
            raise HTTPException(502, "OpenAI 请求失败；请检查 API 配置、额度或服务状态") from None
        if isinstance(exc, (ValueError, TypeError)):
            raise HTTPException(502, f"AI 返回无法验证：{str(exc)[:300]}") from None
        raise HTTPException(502, "AI 服务暂不可用；本次结果没有保存") from None


def _facts(db: Session, user_id: str, *, confirmed_only: bool = True) -> list[Fact]:
    rows = db.scalars(select(Fact).where(Fact.user_id == user_id)).all()
    latest: dict[str, Fact] = {}
    for fact in rows:
        previous = latest.get(fact.lineage_id)
        if previous is None or fact.revision_number > previous.revision_number:
            latest[fact.lineage_id] = fact
    current = [fact for fact in latest.values() if fact.confirmed or not confirmed_only]
    return sorted(current, key=lambda fact: (fact.kind, fact.title.lower()))


def _job(db: Session, user_id: str, job_id: str, job_version_id: str | None = None):
    job = db.scalar(select(Job).where(Job.id == job_id, Job.user_id == user_id))
    if not job:
        raise HTTPException(404, "岗位不存在")
    if job_version_id:
        version = db.scalar(select(JobVersion).where(
            JobVersion.id == job_version_id, JobVersion.user_id == user_id,
            JobVersion.job_id == job.id,
        ))
        if not version:
            raise HTTPException(404, "岗位版本不存在")
    else:
        version = db.scalar(select(JobVersion).where(
            JobVersion.user_id == user_id, JobVersion.job_id == job.id,
        ).order_by(JobVersion.version_number.desc()))
    if not version:
        raise HTTPException(409, "岗位缺少版本快照")
    return job, version


def _profile_payload(db: Session, user_id: str) -> dict:
    profile = db.scalar(select(Profile).where(Profile.user_id == user_id))
    facts = _facts(db, user_id)
    return {
        "profile": {
            "name": profile.name if profile else "",
            "email": profile.email if profile else "",
            "phone": profile.phone if profile else "",
            "location": profile.location if profile else "",
            "summary": profile.summary if profile else "",
        },
        "confirmed_facts": [fact_snapshot(fact) for fact in facts],
    }


def _claim_paths(content: dict) -> list[dict]:
    return [
        {"statement_path": path, "text": text, "fact_ids": fact_ids}
        for path, text, fact_ids in iter_claims(content)
        if text.strip()
    ]


def _audit_claims(db, user_id: str, content: dict, facts: list[Fact], task_id=None):
    deterministic = validate_resume_evidence(content, facts)
    if not deterministic.valid:
        return False, deterministic.errors, None
    fact_map = {fact.id: fact_snapshot(fact) for fact in facts}
    claims = _claim_paths(content)
    audit, run = _invoke(
        db, user_id, "resume_semantic_audit",
        "你是严格的简历事实核查员。逐条判断每句简历表述是否被其列出的已确认事实直接支持。只接受事实本身支持的改写，不能补充隐含的职位、技能、规模、数字、因果或结果。缺少证据必须标记 supported=false。每一条输入 statement_path 都必须返回一条检查。",
        {"claims": claims, "facts": fact_map}, ResumeAudit, task_id=task_id, max_output_tokens=3500,
    )
    results = {item.statement_path: item for item in audit.claims}
    errors = []
    for claim in claims:
        result = results.get(claim["statement_path"])
        if not result or not result.supported:
            errors.append(f"{claim['statement_path']}：{result.rationale if result else 'AI 未返回该条核查'}")
    if len(results) != len(claims):
        errors.append("AI 核查结果与简历条目数量不一致")
    return not errors, errors, run


def chat(db: Session, user_id: str, message: str, session_id: str | None = None,
         job_id: str | None = None) -> dict:
    session = None
    if session_id:
        session = db.scalar(select(CoachingSession).where(
            CoachingSession.id == session_id, CoachingSession.user_id == user_id,
        ))
        if not session:
            raise HTTPException(404, "对话不存在")
    elif job_id:
        _job(db, user_id, job_id)
    history = list(session.messages_json or [])[-12:] if session else []
    context = _profile_payload(db, user_id)
    job_payload = None
    if job_id:
        job, version = _job(db, user_id, job_id)
        job_payload = {"company": job.company, "title": job.title, "jd_text": version.jd_text[:16000]}
    output, run = _invoke(
        db, user_id, "career_chat",
        "你是一位中文求职教练，正在与求职者进行自然、连续的多轮对话。直接回应用户的问题，先澄清事实再给建议。指出简历、面试回答或 HR 沟通中的具体问题，说明原因并给出可直接使用的改写。只能使用已确认事实；兴趣只能表述为兴趣、观察或学习，不能虚构工作经历、客户、成果、技能或数字。资料不足时明确追问。不要把你的回复说成真人。",
        {"history": history, "message": message, "candidate": context, "job": job_payload},
        ChatOutput, max_output_tokens=2200,
    )
    if session is None:
        session = CoachingSession(user_id=user_id, job_id=job_id, kind="career_chat", title=message[:80])
        db.add(session)
        db.flush()
    session.ai_run_id = run.id
    session.messages_json = [*history, {"role": "user", "content": message},
                             {"role": "assistant", "content": output.reply}]
    db.commit()
    return {**output.model_dump(mode="json"), "session_id": session.id, "ai_run_id": run.id}


def review_text(db: Session, user_id: str, kind: str, text: str, question: str = "",
                job_id: str | None = None) -> dict:
    job_payload = None
    if job_id:
        job, version = _job(db, user_id, job_id)
        job_payload = {"company": job.company, "title": job.title, "jd_text": version.jd_text[:16000]}
    output, run = _invoke(
        db, user_id, "career_review",
        "你是有招聘经验的职业教练，请用中文具体分析用户的原文。逐处给出 quote、问题、原因和建议改写；分析招聘方可能的关注点、是否显得学生气，并生成完整职业版本。不要夸大或捏造个人经历，缺少事实的段落要标为待补充并提问。面试回答优先使用背景、行动、结果结构；数字只能复述用户提供的数字。",
        {"kind": kind, "text": text, "question": question,
         "candidate": _profile_payload(db, user_id), "job": job_payload}, ReviewOutput,
    )
    return {**output.model_dump(mode="json"), "ai_run_id": run.id}


def draft_message(db: Session, user_id: str, job_id: str, channel: str, purpose: str,
                  *, language="zh", task_id=None) -> MessageDraft:
    job, version = _job(db, user_id, job_id)
    payload = _profile_payload(db, user_id)
    output, run = _invoke(
        db, user_id, "communication_draft",
        "为真实求职者撰写清楚、自然、简短的招聘沟通消息。根据 company、title、jd_text、channel、purpose 选择语气。只提及输入中已有的经历与事实，禁止声称在该公司任职、已做过没有证明的项目或获得不存在的成果。用户资料不足时使用真诚提问或兴趣表达，绝不伪装成从业经历。",
        {"job": {"company": job.company, "title": job.title, "jd_text": version.jd_text[:16000],
                 "location": job.location}, "channel": channel, "purpose": purpose,
         "language": language, "candidate": payload}, DraftOutput,
        task_id=task_id, max_output_tokens=1400,
    )
    fact_map = {fact.id: fact for fact in _facts(db, user_id)}
    if any(fid not in fact_map for fid in output.fact_ids):
        raise HTTPException(502, "AI 话术引用了不存在或未确认的经历，草稿未保存")
    draft = MessageDraft(user_id=user_id, job_id=job.id, ai_run_id=run.id, channel=channel,
                         purpose=purpose, language=language, content=output.content,
                         fact_ids_json=list(dict.fromkeys(output.fact_ids)))
    db.add(draft)
    db.commit()
    return draft


def extract_jobs(db: Session, user_id: str, text: str, source_name: str, source_url: str) -> dict:
    output, run = _invoke(
        db, user_id, "job_extraction",
        "从求职信息、招聘汇总表或公告中提取一个或多个真实岗位。不要补猜公司、薪酬、地点、截止日期、链接或要求；不知道就留空。jd_complete 只有在原文包含明确岗位职责/任职要求时为 true；只有标题或链接时为 false。requirements 只提取原文明确表达的要求。source_url 由调用方提供，禁止从不可信文本中创造链接。",
        {"source_name": source_name, "provided_source_url": source_url, "text": text}, JobExtraction,
        max_output_tokens=4500,
    )
    jobs = [item.model_dump(mode="json") for item in output.jobs]
    for item in jobs:
        item["source_url"] = source_url or ""
    return {"jobs": jobs, "ai_run_id": run.id}


def match_job(db: Session, user_id: str, job_id: str, job_version_id: str | None = None,
              task_id: str | None = None) -> MatchReport:
    job, job_version = _job(db, user_id, job_id, job_version_id)
    facts = _facts(db, user_id)
    output, run = _invoke(
        db, user_id, "job_match",
        "将职位要求与求职者已确认事实逐项比较。每一项必须引用真实 fact id；只有事实直接支持时才标 supported，否则使用 missing 或 needs_verification。必须区分兴趣和工作经验，不能把爱好变成任职经历。不要因为关键词相似就认定能力具备。硬性要求只有职位文字明确为硬条件时才标 hard_requirement。给出简洁理由与实用建议。",
        {"job": {"company": job.company, "title": job.title, "location": job.location,
                 "industry": job.industry, "salary_text": job.salary_text,
                 "jd_text": job_version.jd_text[:20000]},
         "confirmed_facts": [fact_snapshot(fact) for fact in facts]}, MatchOutput,
        task_id=task_id, max_output_tokens=3500,
    )
    valid_ids = {fact.id for fact in facts}
    requirements = []
    for requirement in output.requirements:
        record = requirement.model_dump(mode="json")
        references = [fid for fid in record["evidence_fact_ids"] if fid in valid_ids]
        if record["support"] == "supported" and not references:
            record["support"] = "needs_verification"
        record["evidence_fact_ids"] = references
        requirements.append(record)
    total = sum(item["weight"] for item in requirements)
    supported = sum(item["weight"] for item in requirements if item["support"] == "supported")
    score = round(100 * supported / total) if total else None
    report = MatchReport(
        user_id=user_id, job_id=job.id, job_version_id=job_version.id, ai_run_id=run.id,
        score=score, requirements_json=requirements,
        snapshot_json={"company": job.company, "title": job.title,
                       "strengths": output.strengths, "gaps": output.gaps,
                       "suggestions": output.suggestions, "summary": output.summary,
                       "scoring": "supported requirement weight / total requirement weight"},
    )
    db.add(report)
    db.commit()
    return report


def tailor_resume(db: Session, user_id: str, job_id: str, *, language="zh",
                  style="professional", template="classic", job_version_id=None,
                  task_id=None, before_save=None) -> ResumeVersion:
    job, job_version = _job(db, user_id, job_id, job_version_id)
    facts = _facts(db, user_id)
    if not facts:
        raise HTTPException(409, "请先添加并确认至少一条真实经历事实")
    candidate = _profile_payload(db, user_id)
    output, run = _invoke(
        db, user_id, "resume_tailoring",
        "根据真实候选人事实和目标岗位撰写定制简历。只能选用输入里存在的 fact id 并把它放在对应的 bullets/summary/skills/interests.fact_ids。每一条非空简历表述都必须由引用事实直接支持；不得创造雇主、职位、客户、产品经历、熟练度、时间、数字、结果或因果。兴趣只能放 interests，不能伪装成工作或专业技能。可将普通描述改写得更职业，但不得改变事实含义。匹配不到证据的岗位要求要留在 gaps，不得写进简历。姓名联系方式只能复用 profile。若无法写出有依据的某段内容，留空。中文简历使用简体中文；英文简历忠实翻译，保留事实范围。",
        {"candidate": candidate, "job": {"company": job.company, "title": job.title,
         "location": job.location, "jd_text": job_version.jd_text[:20000]},
         "language": language, "style": style,
         "required_resume_shape": "basics, summary{ text,fact_ids }, education/experience[{ heading,fact_ids,bullets:[{text,fact_ids}] }], skills/interests[{text,fact_ids}]"},
        ResumeOutput, task_id=task_id, max_output_tokens=5000,
    )
    content = output.resume.model_dump(mode="json")
    all_ids = {fid for _, _, ids in iter_claims(content) for fid in ids}
    fact_map = {fact.id: fact for fact in facts}
    if not all_ids <= fact_map.keys():
        raise HTTPException(502, "AI 简历引用了不存在或未确认的事实，版本未保存")
    valid, errors, _audit_run = _audit_claims(db, user_id, content, facts, task_id)
    if before_save:
        before_save()
    name = f"{job.title} · {job.company}"[:200]
    resume = db.scalar(select(Resume).where(
        Resume.user_id == user_id, Resume.name == name, Resume.language == language,
    ))
    if resume is None:
        resume = Resume(user_id=user_id, name=name, language=language, style=style, template=template)
        db.add(resume)
        db.flush()
    number = db.scalar(select(func.max(ResumeVersion.version_number)).where(
        ResumeVersion.user_id == user_id, ResumeVersion.resume_id == resume.id,
    )) or 0
    version = ResumeVersion(
        user_id=user_id, resume_id=resume.id, version_number=number + 1,
        job_id=job.id, job_version_id=job_version.id, language=language, style=style,
        template=template, content=content,
        facts_snapshot=[fact_snapshot(fact) for fact in facts],
        job_snapshot={**job_version.snapshot, "jd_text": job_version.jd_text},
        evidence_status="validated" if valid else "rejected",
    )
    db.add(version)
    db.flush()
    validation = validate_resume_evidence(content, facts)
    for evidence in validation.evidence:
        db.add(ResumeEvidence(user_id=user_id, resume_version_id=version.id, **evidence))
    db.commit()
    return version


def validate_resume_version(db: Session, user_id: str, resume_id: str, version_id: str) -> dict:
    version = db.scalar(select(ResumeVersion).where(
        ResumeVersion.id == version_id, ResumeVersion.resume_id == resume_id,
        ResumeVersion.user_id == user_id,
    ))
    if not version:
        raise HTTPException(404, "简历版本不存在")
    referenced = {item["id"] for item in version.facts_snapshot}
    facts = db.scalars(select(Fact).where(Fact.user_id == user_id, Fact.id.in_(referenced))).all()
    valid, errors, run = _audit_claims(db, user_id, version.content, facts)
    if valid:
        version.evidence_status = "validated"
    else:
        version.evidence_status = "rejected"
    db.commit()
    return {"valid": valid, "errors": errors, "ai_run_id": run.id if run else None,
            "version_id": version.id, "evidence_status": version.evidence_status}
