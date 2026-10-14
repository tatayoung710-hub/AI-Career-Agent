BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 0001

CREATE TABLE users (
    id VARCHAR(36) NOT NULL, 
    email VARCHAR(254) NOT NULL, 
    password_hash VARCHAR(255) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_users PRIMARY KEY (id), 
    CONSTRAINT uq_users_email UNIQUE (email)
);

CREATE TABLE documents (
    filename VARCHAR(255) NOT NULL, 
    content_type VARCHAR(150) NOT NULL, 
    storage_path TEXT NOT NULL, 
    sha256 VARCHAR(64) NOT NULL, 
    size_bytes INTEGER NOT NULL, 
    status VARCHAR(30) NOT NULL, 
    parsed_text TEXT NOT NULL, 
    parser_version VARCHAR(50) NOT NULL, 
    error TEXT, 
    id VARCHAR(36) NOT NULL, 
    user_id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_documents PRIMARY KEY (id), 
    CONSTRAINT fk_documents_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT uq_documents_user_id UNIQUE (user_id, id)
);

CREATE INDEX ix_documents_sha256 ON documents (sha256);

CREATE INDEX ix_documents_user_id ON documents (user_id);

CREATE TABLE policies (
    name VARCHAR(200) NOT NULL, 
    enabled BOOLEAN NOT NULL, 
    daily_target INTEGER NOT NULL, 
    max_attempts_per_day INTEGER NOT NULL, 
    auto_submit BOOLEAN NOT NULL, 
    auto_approve_grounded BOOLEAN NOT NULL, 
    schedule_time VARCHAR(5) NOT NULL, 
    timezone VARCHAR(100) NOT NULL, 
    filters_json JSONB NOT NULL, 
    channels_json JSONB NOT NULL, 
    last_run_at TIMESTAMP WITH TIME ZONE, 
    id VARCHAR(36) NOT NULL, 
    user_id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_policies PRIMARY KEY (id), 
    CONSTRAINT ck_policies_daily_target CHECK (daily_target >= 1 AND daily_target <= 1000), 
    CONSTRAINT ck_policies_daily_attempts CHECK (max_attempts_per_day >= 0 AND max_attempts_per_day <= 1000), 
    CONSTRAINT fk_policies_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT uq_policies_user_id UNIQUE (user_id, id)
);

CREATE INDEX ix_policies_user_id ON policies (user_id);

CREATE TABLE profiles (
    name VARCHAR(100) NOT NULL, 
    email VARCHAR(254) NOT NULL, 
    phone VARCHAR(100) NOT NULL, 
    location VARCHAR(200) NOT NULL, 
    target_roles JSONB NOT NULL, 
    target_locations JSONB NOT NULL, 
    summary TEXT NOT NULL, 
    preferences JSONB NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    user_id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_profiles PRIMARY KEY (id), 
    CONSTRAINT fk_profiles_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT uq_profiles_user_id UNIQUE (user_id, id), 
    CONSTRAINT uq_profiles_user_id UNIQUE (user_id)
);

CREATE INDEX ix_profiles_user_id ON profiles (user_id);

CREATE TABLE resumes (
    name VARCHAR(200) NOT NULL, 
    language VARCHAR(10) NOT NULL, 
    style VARCHAR(50) NOT NULL, 
    template VARCHAR(50) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    user_id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_resumes PRIMARY KEY (id), 
    CONSTRAINT fk_resumes_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT uq_resumes_user_id UNIQUE (user_id, id)
);

CREATE INDEX ix_resumes_user_id ON resumes (user_id);

CREATE TABLE sources (
    name VARCHAR(200) NOT NULL, 
    kind VARCHAR(50) NOT NULL, 
    url TEXT NOT NULL, 
    capability VARCHAR(40) NOT NULL, 
    notes TEXT NOT NULL, 
    last_synced_at TIMESTAMP WITH TIME ZONE, 
    new_jobs_count INTEGER NOT NULL, 
    sync_task_id VARCHAR(36), 
    archived BOOLEAN NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    user_id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_sources PRIMARY KEY (id), 
    CONSTRAINT fk_sources_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT uq_sources_user_id UNIQUE (user_id, id)
);

CREATE INDEX ix_sources_user_id ON sources (user_id);

CREATE TABLE tasks (
    kind VARCHAR(60) NOT NULL, 
    status VARCHAR(30) NOT NULL, 
    input_json JSONB NOT NULL, 
    output_json JSONB NOT NULL, 
    error TEXT, 
    attempts INTEGER NOT NULL, 
    max_attempts INTEGER NOT NULL, 
    idempotency_key VARCHAR(255), 
    scheduled_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    started_at TIMESTAMP WITH TIME ZONE, 
    finished_at TIMESTAMP WITH TIME ZONE, 
    heartbeat_at TIMESTAMP WITH TIME ZONE, 
    lease_expires_at TIMESTAMP WITH TIME ZONE, 
    claimed_by VARCHAR(200), 
    id VARCHAR(36) NOT NULL, 
    user_id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_tasks PRIMARY KEY (id), 
    CONSTRAINT ck_tasks_status CHECK (status IN ('queued','running','retry','succeeded','failed','cancelled')), 
    CONSTRAINT ck_tasks_attempts CHECK (attempts >= 0 AND max_attempts >= 1), 
    CONSTRAINT fk_tasks_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT uq_tasks_user_id UNIQUE (user_id, id), 
    CONSTRAINT uq_tasks_user_id UNIQUE (user_id, idempotency_key)
);

CREATE INDEX ix_tasks_dispatch ON tasks (status, scheduled_at, lease_expires_at);

CREATE INDEX ix_tasks_user_id ON tasks (user_id);

CREATE TABLE ai_runs (
    task_id VARCHAR(36), 
    kind VARCHAR(60) NOT NULL, 
    provider VARCHAR(50) NOT NULL, 
    model VARCHAR(100) NOT NULL, 
    prompt_version VARCHAR(100) NOT NULL, 
    input_json JSONB NOT NULL, 
    output_json JSONB NOT NULL, 
    status VARCHAR(30) NOT NULL, 
    attempt_number INTEGER NOT NULL, 
    input_tokens INTEGER, 
    output_tokens INTEGER, 
    request_id VARCHAR(255), 
    error TEXT, 
    finished_at TIMESTAMP WITH TIME ZONE, 
    id VARCHAR(36) NOT NULL, 
    user_id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_ai_runs PRIMARY KEY (id), 
    CONSTRAINT fk_ai_runs_user_id_tasks FOREIGN KEY(user_id, task_id) REFERENCES tasks (user_id, id), 
    CONSTRAINT fk_ai_runs_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT uq_ai_runs_user_id UNIQUE (user_id, id)
);

CREATE INDEX ix_ai_runs_user_id ON ai_runs (user_id);

CREATE INDEX ix_ai_runs_user_kind ON ai_runs (user_id, kind, created_at);

CREATE TABLE batches (
    policy_id VARCHAR(36) NOT NULL, 
    run_date DATE NOT NULL, 
    status VARCHAR(30) NOT NULL, 
    target_count INTEGER NOT NULL, 
    prepared_count INTEGER NOT NULL, 
    attempted_count INTEGER NOT NULL, 
    confirmed_count INTEGER NOT NULL, 
    filters_snapshot JSONB NOT NULL, 
    channels_snapshot JSONB NOT NULL, 
    policy_snapshot JSONB NOT NULL, 
    error TEXT, 
    finished_at TIMESTAMP WITH TIME ZONE, 
    id VARCHAR(36) NOT NULL, 
    user_id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_batches PRIMARY KEY (id), 
    CONSTRAINT ck_batches_status CHECK (status IN ('queued','running','paused','completed','failed')), 
    CONSTRAINT ck_batches_nonnegative_counters CHECK (prepared_count >= 0 AND attempted_count >= 0 AND confirmed_count >= 0), 
    CONSTRAINT ck_batches_target_count CHECK (target_count >= 1 AND target_count <= 1000), 
    CONSTRAINT fk_batches_user_id_policies FOREIGN KEY(user_id, policy_id) REFERENCES policies (user_id, id), 
    CONSTRAINT fk_batches_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT uq_batches_policy_id UNIQUE (policy_id, run_date), 
    CONSTRAINT uq_batches_user_id UNIQUE (user_id, id)
);

CREATE INDEX ix_batches_user_id ON batches (user_id);

CREATE TABLE facts (
    lineage_id VARCHAR(36) NOT NULL, 
    revision_number INTEGER NOT NULL, 
    supersedes_id VARCHAR(36), 
    document_id VARCHAR(36), 
    kind VARCHAR(30) NOT NULL, 
    title VARCHAR(255) NOT NULL, 
    content TEXT NOT NULL, 
    tags JSONB NOT NULL, 
    source_text TEXT NOT NULL, 
    details JSONB NOT NULL, 
    confirmed BOOLEAN NOT NULL, 
    confirmed_at TIMESTAMP WITH TIME ZONE, 
    id VARCHAR(36) NOT NULL, 
    user_id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_facts PRIMARY KEY (id), 
    CONSTRAINT ck_facts_kind CHECK (kind IN ('education','experience','project','skill','interest','achievement')), 
    CONSTRAINT ck_facts_positive_revision CHECK (revision_number >= 1), 
    CONSTRAINT fk_facts_user_id_documents FOREIGN KEY(user_id, document_id) REFERENCES documents (user_id, id), 
    CONSTRAINT fk_facts_user_id_facts FOREIGN KEY(user_id, supersedes_id) REFERENCES facts (user_id, id), 
    CONSTRAINT fk_facts_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT uq_facts_user_id UNIQUE (user_id, id), 
    CONSTRAINT uq_facts_user_id UNIQUE (user_id, lineage_id, revision_number)
);

CREATE INDEX ix_facts_user_id ON facts (user_id);

CREATE TABLE jobs (
    company VARCHAR(255) NOT NULL, 
    title VARCHAR(255) NOT NULL, 
    location VARCHAR(255) NOT NULL, 
    industry VARCHAR(200) NOT NULL, 
    jd_text TEXT NOT NULL, 
    requirements JSONB NOT NULL, 
    salary_text VARCHAR(255) NOT NULL, 
    source_id VARCHAR(36), 
    source_url TEXT NOT NULL, 
    published_at DATE, 
    deadline DATE, 
    status VARCHAR(30) NOT NULL, 
    version_number INTEGER NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    user_id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_jobs PRIMARY KEY (id), 
    CONSTRAINT ck_jobs_status CHECK (status IN ('active','closed','archived')), 
    CONSTRAINT fk_jobs_user_id_sources FOREIGN KEY(user_id, source_id) REFERENCES sources (user_id, id), 
    CONSTRAINT fk_jobs_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT uq_jobs_user_id UNIQUE (user_id, id)
);

CREATE INDEX ix_jobs_user_id ON jobs (user_id);

CREATE TABLE coaching_sessions (
    job_id VARCHAR(36), 
    ai_run_id VARCHAR(36), 
    kind VARCHAR(40) NOT NULL, 
    title VARCHAR(255) NOT NULL, 
    messages_json JSONB NOT NULL, 
    feedback_json JSONB NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    user_id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_coaching_sessions PRIMARY KEY (id), 
    CONSTRAINT fk_coaching_sessions_user_id_ai_runs FOREIGN KEY(user_id, ai_run_id) REFERENCES ai_runs (user_id, id), 
    CONSTRAINT fk_coaching_sessions_user_id_jobs FOREIGN KEY(user_id, job_id) REFERENCES jobs (user_id, id), 
    CONSTRAINT fk_coaching_sessions_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT uq_coaching_sessions_user_id UNIQUE (user_id, id)
);

CREATE INDEX ix_coaching_sessions_user_id ON coaching_sessions (user_id);

CREATE TABLE job_source_records (
    job_id VARCHAR(36) NOT NULL, 
    source_id VARCHAR(36), 
    source_key VARCHAR(200) NOT NULL, 
    external_key VARCHAR(255) NOT NULL, 
    url TEXT NOT NULL, 
    raw_text TEXT NOT NULL, 
    published_at DATE, 
    id VARCHAR(36) NOT NULL, 
    user_id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_job_source_records PRIMARY KEY (id), 
    CONSTRAINT fk_job_source_records_user_id_jobs FOREIGN KEY(user_id, job_id) REFERENCES jobs (user_id, id), 
    CONSTRAINT fk_job_source_records_user_id_sources FOREIGN KEY(user_id, source_id) REFERENCES sources (user_id, id), 
    CONSTRAINT fk_job_source_records_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT uq_job_source_records_user_id UNIQUE (user_id, id), 
    CONSTRAINT uq_job_source_records_user_id UNIQUE (user_id, source_key, external_key)
);

CREATE INDEX ix_job_source_records_user_id ON job_source_records (user_id);

CREATE TABLE job_versions (
    job_id VARCHAR(36) NOT NULL, 
    version_number INTEGER NOT NULL, 
    jd_text TEXT NOT NULL, 
    requirements JSONB NOT NULL, 
    snapshot JSONB NOT NULL, 
    extraction_version VARCHAR(50) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    user_id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_job_versions PRIMARY KEY (id), 
    CONSTRAINT ck_job_versions_positive_version CHECK (version_number >= 1), 
    CONSTRAINT fk_job_versions_user_id_jobs FOREIGN KEY(user_id, job_id) REFERENCES jobs (user_id, id), 
    CONSTRAINT fk_job_versions_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT uq_job_versions_job_id UNIQUE (job_id, version_number), 
    CONSTRAINT uq_job_versions_user_id UNIQUE (user_id, id), 
    CONSTRAINT uq_job_versions_user_id UNIQUE (user_id, job_id, id)
);

CREATE INDEX ix_job_versions_user_id ON job_versions (user_id);

CREATE TABLE message_drafts (
    job_id VARCHAR(36) NOT NULL, 
    ai_run_id VARCHAR(36), 
    channel VARCHAR(60) NOT NULL, 
    purpose VARCHAR(60) NOT NULL, 
    language VARCHAR(10) NOT NULL, 
    content TEXT NOT NULL, 
    status VARCHAR(30) NOT NULL, 
    fact_ids_json JSONB NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    user_id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_message_drafts PRIMARY KEY (id), 
    CONSTRAINT fk_message_drafts_user_id_ai_runs FOREIGN KEY(user_id, ai_run_id) REFERENCES ai_runs (user_id, id), 
    CONSTRAINT fk_message_drafts_user_id_jobs FOREIGN KEY(user_id, job_id) REFERENCES jobs (user_id, id), 
    CONSTRAINT fk_message_drafts_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT uq_message_drafts_user_id UNIQUE (user_id, id)
);

CREATE INDEX ix_message_drafts_user_id ON message_drafts (user_id);

CREATE TABLE resume_versions (
    resume_id VARCHAR(36) NOT NULL, 
    version_number INTEGER NOT NULL, 
    parent_version_id VARCHAR(36), 
    job_id VARCHAR(36), 
    job_version_id VARCHAR(36), 
    language VARCHAR(10) NOT NULL, 
    style VARCHAR(50) NOT NULL, 
    template VARCHAR(50) NOT NULL, 
    schema_version VARCHAR(30) NOT NULL, 
    content JSONB NOT NULL, 
    facts_snapshot JSONB NOT NULL, 
    job_snapshot JSONB NOT NULL, 
    evidence_status VARCHAR(30) NOT NULL, 
    approved_at TIMESTAMP WITH TIME ZONE, 
    approval_source VARCHAR(40) NOT NULL, 
    approval_policy_snapshot JSONB NOT NULL, 
    export_status VARCHAR(30) NOT NULL, 
    export_path TEXT, 
    id VARCHAR(36) NOT NULL, 
    user_id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_resume_versions PRIMARY KEY (id), 
    CONSTRAINT ck_resume_versions_evidence_status CHECK (evidence_status IN ('pending','validated','rejected')), 
    CONSTRAINT ck_resume_versions_language CHECK (language IN ('zh','en')), 
    CONSTRAINT ck_resume_versions_positive_version CHECK (version_number >= 1), 
    CONSTRAINT fk_resume_versions_user_id_job_versions FOREIGN KEY(user_id, job_id, job_version_id) REFERENCES job_versions (user_id, job_id, id), 
    CONSTRAINT fk_resume_versions_user_id_resume_versions FOREIGN KEY(user_id, parent_version_id) REFERENCES resume_versions (user_id, id), 
    CONSTRAINT fk_resume_versions_user_id_resumes FOREIGN KEY(user_id, resume_id) REFERENCES resumes (user_id, id), 
    CONSTRAINT fk_resume_versions_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT uq_resume_versions_resume_id UNIQUE (resume_id, version_number), 
    CONSTRAINT uq_resume_versions_user_id UNIQUE (user_id, id), 
    CONSTRAINT uq_resume_versions_user_id UNIQUE (user_id, resume_id, id)
);

CREATE INDEX ix_resume_versions_user_id ON resume_versions (user_id);

CREATE TABLE applications (
    job_id VARCHAR(36) NOT NULL, 
    resume_version_id VARCHAR(36), 
    attempt_no INTEGER NOT NULL, 
    status VARCHAR(30) NOT NULL, 
    applied_at DATE, 
    hr_name VARCHAR(100) NOT NULL, 
    hr_contact VARCHAR(255) NOT NULL, 
    notes TEXT NOT NULL, 
    version INTEGER NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    user_id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_applications PRIMARY KEY (id), 
    CONSTRAINT ck_applications_status CHECK (status IN ('pending','applied','hr_chat','interview_1','interview_2','offer','rejected','withdrawn')), 
    CONSTRAINT ck_applications_positive_attempt CHECK (attempt_no >= 1), 
    CONSTRAINT fk_applications_user_id_jobs FOREIGN KEY(user_id, job_id) REFERENCES jobs (user_id, id), 
    CONSTRAINT fk_applications_user_id_resume_versions FOREIGN KEY(user_id, resume_version_id) REFERENCES resume_versions (user_id, id), 
    CONSTRAINT fk_applications_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT uq_applications_user_id UNIQUE (user_id, id), 
    CONSTRAINT uq_applications_user_id UNIQUE (user_id, job_id, attempt_no)
);

CREATE INDEX ix_applications_user_id ON applications (user_id);

CREATE TABLE batch_items (
    batch_id VARCHAR(36) NOT NULL, 
    job_id VARCHAR(36) NOT NULL, 
    job_version_id VARCHAR(36) NOT NULL, 
    resume_version_id VARCHAR(36), 
    task_id VARCHAR(36), 
    channel VARCHAR(60) NOT NULL, 
    capability VARCHAR(60) NOT NULL, 
    status VARCHAR(40) NOT NULL, 
    prepared_at TIMESTAMP WITH TIME ZONE, 
    attempted_at TIMESTAMP WITH TIME ZONE, 
    confirmed_at TIMESTAMP WITH TIME ZONE, 
    artifact_path TEXT, 
    artifact_sha256 VARCHAR(64), 
    receipt_json JSONB NOT NULL, 
    error TEXT, 
    id VARCHAR(36) NOT NULL, 
    user_id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_batch_items PRIMARY KEY (id), 
    CONSTRAINT fk_batch_items_user_id_batches FOREIGN KEY(user_id, batch_id) REFERENCES batches (user_id, id), 
    CONSTRAINT fk_batch_items_user_id_job_versions FOREIGN KEY(user_id, job_id, job_version_id) REFERENCES job_versions (user_id, job_id, id), 
    CONSTRAINT fk_batch_items_user_id_resume_versions FOREIGN KEY(user_id, resume_version_id) REFERENCES resume_versions (user_id, id), 
    CONSTRAINT fk_batch_items_user_id_tasks FOREIGN KEY(user_id, task_id) REFERENCES tasks (user_id, id), 
    CONSTRAINT fk_batch_items_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT uq_batch_items_batch_id UNIQUE (batch_id, job_id), 
    CONSTRAINT uq_batch_items_user_id UNIQUE (user_id, id)
);

CREATE INDEX ix_batch_items_dispatch ON batch_items (batch_id, status);

CREATE INDEX ix_batch_items_user_id ON batch_items (user_id);

CREATE TABLE match_reports (
    job_id VARCHAR(36) NOT NULL, 
    job_version_id VARCHAR(36) NOT NULL, 
    resume_version_id VARCHAR(36), 
    ai_run_id VARCHAR(36), 
    score INTEGER, 
    requirements_json JSONB NOT NULL, 
    snapshot_json JSONB NOT NULL, 
    scoring_version VARCHAR(60) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    user_id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_match_reports PRIMARY KEY (id), 
    CONSTRAINT ck_match_reports_score CHECK (score IS NULL OR (score >= 0 AND score <= 100)), 
    CONSTRAINT fk_match_reports_user_id_ai_runs FOREIGN KEY(user_id, ai_run_id) REFERENCES ai_runs (user_id, id), 
    CONSTRAINT fk_match_reports_user_id_job_versions FOREIGN KEY(user_id, job_id, job_version_id) REFERENCES job_versions (user_id, job_id, id), 
    CONSTRAINT fk_match_reports_user_id_resume_versions FOREIGN KEY(user_id, resume_version_id) REFERENCES resume_versions (user_id, id), 
    CONSTRAINT fk_match_reports_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT uq_match_reports_user_id UNIQUE (user_id, id)
);

CREATE INDEX ix_match_reports_user_id ON match_reports (user_id);

CREATE TABLE resume_evidence (
    resume_version_id VARCHAR(36) NOT NULL, 
    fact_id VARCHAR(36) NOT NULL, 
    statement_path VARCHAR(255) NOT NULL, 
    statement_text TEXT NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    user_id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_resume_evidence PRIMARY KEY (id), 
    CONSTRAINT fk_resume_evidence_user_id_facts FOREIGN KEY(user_id, fact_id) REFERENCES facts (user_id, id), 
    CONSTRAINT fk_resume_evidence_user_id_resume_versions FOREIGN KEY(user_id, resume_version_id) REFERENCES resume_versions (user_id, id), 
    CONSTRAINT fk_resume_evidence_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT uq_resume_evidence_resume_version_id UNIQUE (resume_version_id, statement_path, fact_id), 
    CONSTRAINT uq_resume_evidence_user_id UNIQUE (user_id, id)
);

CREATE INDEX ix_resume_evidence_user_id ON resume_evidence (user_id);

CREATE TABLE application_events (
    application_id VARCHAR(36) NOT NULL, 
    sequence INTEGER NOT NULL, 
    from_status VARCHAR(30), 
    to_status VARCHAR(30) NOT NULL, 
    notes TEXT NOT NULL, 
    occurred_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    user_id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_application_events PRIMARY KEY (id), 
    CONSTRAINT fk_application_events_user_id_applications FOREIGN KEY(user_id, application_id) REFERENCES applications (user_id, id), 
    CONSTRAINT fk_application_events_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT uq_application_events_application_id UNIQUE (application_id, sequence), 
    CONSTRAINT uq_application_events_user_id UNIQUE (user_id, id)
);

CREATE INDEX ix_application_events_user_id ON application_events (user_id);

INSERT INTO alembic_version (version_num) VALUES ('0001') RETURNING alembic_version.version_num;

-- Running upgrade 0001 -> 0002

CREATE FUNCTION career_guard_immutable_payload() RETURNS trigger AS $$
        BEGIN
            IF (to_jsonb(NEW) - string_to_array(TG_ARGV[0], ','))
               IS DISTINCT FROM (to_jsonb(OLD) - string_to_array(TG_ARGV[0], ',')) THEN
                RAISE EXCEPTION '% payload is immutable; create a new revision', TG_TABLE_NAME
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;;

CREATE TRIGGER guard_facts_payload BEFORE UPDATE ON facts FOR EACH ROW EXECUTE FUNCTION career_guard_immutable_payload('confirmed,confirmed_at');

CREATE TRIGGER guard_job_versions_payload BEFORE UPDATE ON job_versions FOR EACH ROW EXECUTE FUNCTION career_guard_immutable_payload('');

CREATE TRIGGER guard_resume_versions_payload BEFORE UPDATE ON resume_versions FOR EACH ROW EXECUTE FUNCTION career_guard_immutable_payload('evidence_status,approved_at,approval_source,approval_policy_snapshot,export_status,export_path');

CREATE TRIGGER guard_resume_evidence_payload BEFORE UPDATE ON resume_evidence FOR EACH ROW EXECUTE FUNCTION career_guard_immutable_payload('');

UPDATE alembic_version SET version_num='0002' WHERE alembic_version.version_num = '0001';

-- Running upgrade 0002 -> 0003

ALTER TABLE jobs ADD COLUMN jd_complete BOOLEAN DEFAULT true NOT NULL;

UPDATE jobs SET jd_complete = FALSE WHERE jd_text LIKE '%ԭ����δ�ṩ���� JD%';

UPDATE alembic_version SET version_num='0003' WHERE alembic_version.version_num = '0002';

COMMIT;

