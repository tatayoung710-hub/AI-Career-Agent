"""Authenticated, structured AI services; no successful demo fallbacks."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.ai import service
from app.ai.api_schemas import (
    ChatInput,
    DraftInput,
    ExtractInput,
    MatchInput,
    ReviewInput,
    TailorInput,
    ValidateInput,
)
from app.auth import get_current_user
from app.core_routes import serialize
from app.db import get_db
from app.models import User

router = APIRouter(prefix="/ai", tags=["AI"])


@router.post("/chat")
def chat(payload: ChatInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.chat(db, user.id, payload.message, payload.session_id, payload.job_id)


@router.post("/review")
def review(payload: ReviewInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.review_text(db, user.id, payload.kind, payload.text, payload.question, payload.job_id)


@router.post("/draft")
def draft(payload: DraftInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    record = service.draft_message(db, user.id, payload.job_id, payload.channel,
                                   payload.purpose, language=payload.language)
    return serialize(record)


@router.post("/extract-jobs")
def extract(payload: ExtractInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.extract_jobs(db, user.id, payload.text, payload.source_name, payload.source_url)


@router.post("/match")
def match(payload: MatchInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    report = service.match_job(db, user.id, payload.job_id)
    return {**serialize(report), **report.snapshot_json}


@router.post("/tailor")
def tailor(payload: TailorInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    version = service.tailor_resume(
        db, user.id, payload.job_id, language=payload.language, style=payload.style,
        template=payload.template,
    )
    return {**serialize(version, exclude=("export_path",)),
            "validation": {"valid": version.evidence_status == "validated",
                           "errors": [] if version.evidence_status == "validated"
                           else ["部分简历表述未通过事实核查，请在编辑器中检查后重新验证"]}}


@router.post("/validate-resume")
def validate(payload: ValidateInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.validate_resume_version(db, user.id, payload.resume_id, payload.version_id)
