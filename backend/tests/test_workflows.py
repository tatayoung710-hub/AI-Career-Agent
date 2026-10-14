from app.ai.evidence import validate_resume_evidence
from app.models import Fact

from conftest import make_resume


def test_resume_evidence_rejects_unconfirmed_and_interest_as_work():
    interest = Fact(id="interest-1", user_id="u", kind="interest", title="Google 产品",
                    content="关注 Google 产品体验", source_text="用户描述", details={},
                    confirmed=True, lineage_id="l", revision_number=1)
    resume = make_resume(interest.id, text="")
    resume["experience"] = [{
        "heading": "工作经历", "fact_ids": [interest.id],
        "bullets": [{"text": "曾在 Google 工作", "fact_ids": [interest.id]}],
    }]
    result = validate_resume_evidence(resume, [interest])
    assert not result.valid
    assert any("不能转换成任职经历" in error for error in result.errors)


def test_resume_evidence_rejects_unsupported_numbers():
    fact = Fact(id="fact-1", user_id="u", kind="project", title="课程资料",
                content="协助整理课程资料", source_text="", details={}, confirmed=True,
                lineage_id="l", revision_number=1)
    result = validate_resume_evidence(make_resume(fact.id, text="整理 100 份课程资料"), [fact])
    assert not result.valid
    assert any("没有事实依据的数字" in error for error in result.errors)


def test_resume_evidence_requires_confirmed_referenced_fact():
    fact = Fact(id="fact-1", user_id="u", kind="project", title="课程资料",
                content="协助整理课程资料", source_text="", details={}, confirmed=False,
                lineage_id="l", revision_number=1)
    result = validate_resume_evidence(make_resume(fact.id), [fact])
    assert not result.valid
    assert any("未经确认" in error for error in result.errors)


def test_core_job_resume_application_and_daily_batch_are_owner_scoped(registered):
    client = registered
    source = client.post("/api/v1/sources/catalog").json()
    assert source["created"] >= 8
    uploaded = client.post("/api/v1/documents", files={
        "file": ("resume.txt", "协助老师整理课程资料".encode(), "text/plain"),
    })
    assert uploaded.status_code == 201
    assert "整理课程资料" in uploaded.json()["parsed_text"]
    fact = client.post("/api/v1/facts", json={
        "kind": "project", "title": "课程资料整理", "content": "协助老师整理课程资料",
    }).json()
    assert client.post(f"/api/v1/facts/{fact['id']}/confirm").status_code == 200
    job = client.post("/api/v1/jobs", json={
        "company": "Example Co", "title": "运营助理", "jd_text": "协助项目运营和资料整理",
    }).json()
    application = client.post("/api/v1/applications", json={"job_id": job["id"]}).json()
    changed = client.patch(f"/api/v1/applications/{application['id']}", json={
        "version": application["version"], "status": "applied", "hr_name": "HR",
    })
    assert changed.status_code == 200
    stale = client.patch(f"/api/v1/applications/{application['id']}", json={
        "version": application["version"], "status": "hr_chat",
    })
    assert stale.status_code == 409
    policy = client.post("/api/v1/automation/policies", json={
        "name": "1000-job daily queue", "daily_target": 1000, "channels_json": ["prepare_open"],
    })
    assert policy.status_code == 201
    first = client.post("/api/v1/automation/run", json={"policy_id": policy.json()["id"]})
    second = client.post("/api/v1/automation/run", json={"policy_id": policy.json()["id"]})
    assert first.status_code == second.status_code == 202
    assert first.json()["id"] == second.json()["id"]


def test_ai_unconfigured_returns_clear_error(registered, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "openai_api_key", "")
    response = registered.post("/api/v1/ai/chat", json={"message": "帮我分析面试回答"})
    assert response.status_code == 503
    assert "OPENAI_API_KEY" in response.json()["detail"]
