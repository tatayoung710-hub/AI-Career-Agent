"""Deterministic evidence checks, also applied immediately before export/send.

Reference validity cannot prove natural-language entailment: generation additionally
uses a separate semantic assessment and retains user/policy approval provenance.
"""

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from app.ai.schemas import ResumeContent


@dataclass
class EvidenceValidation:
    valid: bool
    errors: list[str] = field(default_factory=list)
    evidence: list[dict] = field(default_factory=list)


def fact_snapshot(fact: Any) -> dict:
    if isinstance(fact, dict):
        return fact
    return {
        "id": fact.id, "kind": fact.kind, "title": fact.title,
        "content": fact.content, "source_text": fact.source_text,
        "details": fact.details, "confirmed": fact.confirmed,
        "lineage_id": fact.lineage_id, "revision_number": fact.revision_number,
    }


def fact_text(fact: dict) -> str:
    return " ".join([
        str(fact.get("title", "")), str(fact.get("content", "")),
        str(fact.get("source_text", "")),
        json.dumps(fact.get("details", {}), ensure_ascii=False),
    ])


def iter_claims(content: dict):
    summary = content.get("summary", {})
    yield "summary", summary.get("text", ""), summary.get("fact_ids", [])
    for section in ("education", "experience"):
        for index, item in enumerate(content.get(section, [])):
            path = f"{section}.{index}"
            yield f"{path}.heading", item.get("heading", ""), item.get("fact_ids", [])
            for bullet_index, bullet in enumerate(item.get("bullets", [])):
                yield (
                    f"{path}.bullets.{bullet_index}",
                    bullet.get("text", ""), bullet.get("fact_ids", []),
                )
    for section in ("skills", "interests"):
        for index, item in enumerate(content.get(section, [])):
            yield f"{section}.{index}", item.get("text", ""), item.get("fact_ids", [])


def validate_resume_evidence(content: dict, facts: Sequence[Any]) -> EvidenceValidation:
    try:
        parsed = ResumeContent.model_validate(content).model_dump()
    except ValidationError as exc:
        return EvidenceValidation(False, [f"简历结构错误：{e['loc']} {e['msg']}" for e in exc.errors()])
    fact_map = {f["id"]: f for f in map(fact_snapshot, facts)}
    errors: list[str] = []
    evidence: list[dict] = []
    number_pattern = re.compile(r"\d+(?:[.,]\d+)*(?:%|％)?")
    for path, text, fact_ids in iter_claims(parsed):
        if not text.strip():
            continue
        if not fact_ids:
            errors.append(f"{path}：非空表述缺少事实引用")
            continue
        unknown = [fid for fid in fact_ids if fid not in fact_map]
        if unknown:
            errors.append(f"{path}：包含不存在或不属于当前用户的事实引用")
            continue
        refs = [fact_map[fid] for fid in fact_ids]
        if any(not f.get("confirmed") for f in refs):
            errors.append(f"{path}：引用未经确认的事实")
        kinds = {f.get("kind") for f in refs}
        if path.startswith("education.") and kinds != {"education"}:
            errors.append(f"{path}：教育信息必须来自教育事实")
        if path.startswith("experience.") and not kinds <= {"experience", "project", "achievement"}:
            errors.append(f"{path}：兴趣、技能或教育不能转换成任职经历")
        if path.startswith("skills.") and kinds == {"interest"}:
            errors.append(f"{path}：兴趣不能直接证明技能")
        source_numbers = set(number_pattern.findall(" ".join(fact_text(f) for f in refs)))
        new_numbers = set(number_pattern.findall(text)) - source_numbers
        if new_numbers:
            errors.append(f"{path}：出现没有事实依据的数字 {', '.join(sorted(new_numbers))}")
        if re.search(r"\[\s*(?:待|补充|填写)|TODO|TBD|<insert", text, re.IGNORECASE):
            errors.append(f"{path}：包含待补充占位符")
        for fact_id in dict.fromkeys(fact_ids):
            evidence.append({"statement_path": path, "statement_text": text, "fact_id": fact_id})
    return EvidenceValidation(not errors, errors, evidence)
