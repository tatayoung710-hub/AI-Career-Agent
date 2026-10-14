# Implementation contract

Local repository: `ai-career-agent`. React/TypeScript/Tailwind frontend and FastAPI backend.
API prefix `/api/v1`; JSON property names use snake_case. Authentication uses Bearer tokens.
No private data or API keys are committed. Demo records must be visibly fictional.

## Task architecture

PostgreSQL is the production database. SQLite is an explicit single-worker local development option.
Use a durable `tasks` ledger and separate Python worker, with transactional claims, leases,
bounded retries and PostgreSQL `FOR UPDATE SKIP LOCKED`. This refines the preliminary Redis/Celery
proposal: 1,000 daily jobs do not need a second queue service. The database is the source of truth.
API requests enqueue work; the independent worker performs AI and export/batch preparation.
Daily scheduler uses Asia/Shanghai and a unique policy/date batch identity.

## Public contracts

- `POST /auth/register`, `POST /auth/login`: JSON email/password; token response.
- `GET /auth/me`; `GET/PATCH /profile`.
- `GET/POST /facts`; facts are immutable revisions. `POST /facts/{id}/confirm`.
- `GET/POST /documents` (POST multipart file); `GET /documents/{id}`.
- `GET/POST /sources`, `PATCH/DELETE /sources/{id}`; `POST /sources/{id}/sync`.
- `GET/POST /jobs`, `GET/PATCH /jobs/{id}`; `POST /jobs/import` for CSV/XLSX.
- `GET/POST /resumes`; `GET /resumes/{id}`; `GET/POST /resumes/{id}/versions`.
- `POST /resumes/{id}/versions/{version_id}/approve`; version export endpoint.
- `GET/POST /applications`, `PATCH /applications/{id}`, `GET /applications/{id}/events`.
- `POST /ai/chat`: message, history [{role,content}], optional job_id.
- `POST /ai/review`: kind (resume/interview/hr), text, optional job_id.
- `POST /ai/draft`: channel, purpose, job_id.
- `POST /ai/extract-jobs`: text, optional source_id; returns editable previews.
- `POST /ai/match`: job_id, optional resume_version_id.
- `POST /ai/tailor`: job_id, language (zh/en), style; returns resume/version.
- `GET/POST /automation/policies`; `PATCH /automation/policies/{id}`.
- `POST /automation/run`: policy_id; `GET /automation/batches`; batch items/detail/pause.
- `GET /tasks`, `GET /tasks/{id}`, `GET /advice`.

Errors use FastAPI `detail`. Frontend must display provider-not-configured errors, never silently
fabricate AI output. Model structured output requires semantic evidence validation too.

Resume content: basics (name/email/phone/location), summary {text,fact_ids}, education[], experience[]
with heading, fact_ids and bullets [{text,fact_ids}], skills/interests [{text,fact_ids}]. Each generated factual
claim references a confirmed immutable fact. Human-confirmed is not independently verified.

Daily target is up to 1,000. Preparation, submission attempts and verified receipts are distinct.
Never implement a fake successful submission adapter. Unpermitted BOSS/small-program channels
remain prepare/open-entry only. Platform capability and per-job attachment support need verification.
No CAPTCHA solving, quota circumvention or blind retries after uncertain external submissions.

Owner boundaries: backend schema/core API owner writes models, db/config/auth/core routers;
AI/automation owner writes provider, evidence/scoring, AI routes, scheduler, worker and channels;
frontend owner writes frontend only. Root owns integration, tests, deployment and documentation.
