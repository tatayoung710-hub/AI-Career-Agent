# Database schema

Production uses PostgreSQL; SQLite is an explicit local, single-worker development option.
Both databases are built with Alembic migrations, never application-startup `create_all`.

Run from `backend/`:

```text
python -m alembic upgrade head
python -m alembic current
```

`DATABASE_URL` selects the database. All primary keys are UUID strings. Timestamps are UTC;
policy scheduling and batch dates use the policy timezone, initially `Asia/Shanghai`.
JSON fields use PostgreSQL JSONB with a SQLite JSON variant. Frequently filtered ownership,
status, dates and relationships have relational columns and indexes.

## Entity groups

| Table | Purpose |
| --- | --- |
| users / profiles | Identity, password hash, contact fields and career preferences |
| documents | Uploaded file metadata, private storage path, hash, parsed text and parse status |
| facts | Immutable factual revisions with original evidence and human confirmation |
| sources | User's source library and declared integration capability |
| jobs / job_versions | Current job projection and immutable JD snapshots |
| job_source_records | Provenance and source-specific deduplication keys for a canonical job |
| resumes / resume_versions | Resume family and immutable, job-specific content snapshots |
| resume_evidence | Statement-to-confirmed-fact references, with ownership foreign keys |
| applications / application_events | Current application state and transactionally recorded history |
| ai_runs / match_reports | Provider execution audit and versioned evidence-based matching results |
| message_drafts / coaching_sessions | Generated communication drafts and coaching history |
| policies / batches / batch_items | Durable daily preparation/submission manifests |
| tasks | Database-backed work queue with scheduled retries, claims and leases |

## Isolation and invariants

Every business entity has a non-null `user_id`. Owner-scoped parents declare
`UNIQUE(user_id, id)`. Important child relationships use composite foreign keys so a row
cannot associate one user's resume, job, fact, application or task with another user's entity.
The service layer additionally filters reads by authenticated ownership, including downloads.

Fact revisions share a `lineage_id` and an increasing `revision_number`; revisions reference
their predecessor through `supersedes_id`. A confirmation means the user accepted the fact,
not that an outside institution verified it. To correct content, create a new revision.

`0002_immutable_evidence` installs database triggers for fact payloads, job snapshots,
resume content/snapshots and statement evidence. Confirmation fields, evidence-validation
status, approval audit and export status can change without replacing content. Generated
factual claims require explicit confirmed fact references plus semantic validation; foreign
keys alone cannot prove natural-language fidelity.

Job updates create a new `job_versions` row. Resume versions reference the exact job version,
carry `facts_snapshot` and `job_snapshot`, and retain template/schema versions. Resume editing
creates another version. Approved versions record `approval_source` and, for explicitly enabled
policy approval, `approval_policy_snapshot`.

Application statuses are `pending`, `applied`, `hr_chat`, `interview_1`, `interview_2`,
`offer`, `rejected`, `withdrawn`. `(user_id, job_id, attempt_no)` is unique so reapplication
can be recorded without losing the previous cycle. Status updates and sequence-numbered
events commit together; the service checks `version` to reject stale concurrent edits.

Daily batches are unique by `(policy_id, run_date)`. Policies cap preparation and submission
attempt targets at 1,000, rather than claiming 1,000 platform-confirmed submissions.
Each batch has at most one item per canonical job. Prepared, attempted and confirmed counts
remain distinct, and receipt payloads identify what the external service actually acknowledged.
SMTP acceptance is not evidence of employer application receipt.

Tasks are claimed with a lease and attempt count. PostgreSQL workers use row locking and
`SKIP LOCKED`; SQLite is not a replacement for multi-worker production execution. A unique
owner-scoped idempotency key protects logical enqueueing. External submissions still need
receipts and reconciliation: after an ambiguous timeout, blind retry can duplicate a submission.
An API provider timeout can also cause repeated billable calls; internal idempotency cannot
provide an exactly-once guarantee across an external service.

## Migration history

- `0001_initial_schema`: frozen table, index, unique, check and foreign-key definitions.
- `0002_immutable_evidence`: reversible PostgreSQL/SQLite immutability triggers.
- `0003_job_completeness`: distinguish incomplete imported leads from usable job descriptions.

Future model changes require a new reviewed revision. Existing migrations do not import live
ORM metadata to create tables, so changing a model cannot silently rewrite migration history.
