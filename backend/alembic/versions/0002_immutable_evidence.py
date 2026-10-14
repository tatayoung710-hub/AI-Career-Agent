"""Protect factual payloads and version snapshots from in-place mutation.

Revision ID: 0002
Revises: 0001
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

# This list is frozen migration history, not imported from current ORM models.
IMMUTABLE_COLUMNS = {
    "facts": (
        "id",
        "user_id",
        "created_at",
        "lineage_id",
        "revision_number",
        "supersedes_id",
        "document_id",
        "kind",
        "title",
        "content",
        "tags",
        "source_text",
        "details",
    ),
    "job_versions": (
        "id",
        "user_id",
        "created_at",
        "job_id",
        "version_number",
        "jd_text",
        "requirements",
        "snapshot",
        "extraction_version",
    ),
    "resume_versions": (
        "id",
        "user_id",
        "created_at",
        "resume_id",
        "version_number",
        "parent_version_id",
        "job_id",
        "job_version_id",
        "language",
        "style",
        "template",
        "schema_version",
        "content",
        "facts_snapshot",
        "job_snapshot",
    ),
    "resume_evidence": (
        "id",
        "user_id",
        "created_at",
        "resume_version_id",
        "fact_id",
        "statement_path",
        "statement_text",
    ),
}

ALLOWED_UPDATES = {
    "facts": "confirmed,confirmed_at",
    "job_versions": "",
    "resume_versions": (
        "evidence_status,approved_at,approval_source,approval_policy_snapshot,"
        "export_status,export_path"
    ),
    "resume_evidence": "",
}


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("""
        CREATE FUNCTION career_guard_immutable_payload() RETURNS trigger AS $$
        BEGIN
            IF (to_jsonb(NEW) - string_to_array(TG_ARGV[0], ','))
               IS DISTINCT FROM (to_jsonb(OLD) - string_to_array(TG_ARGV[0], ',')) THEN
                RAISE EXCEPTION '% payload is immutable; create a new revision', TG_TABLE_NAME
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """)
        for table, allowed in ALLOWED_UPDATES.items():
            op.execute(
                f"CREATE TRIGGER guard_{table}_payload BEFORE UPDATE ON {table} "
                "FOR EACH ROW EXECUTE FUNCTION "
                f"career_guard_immutable_payload('{allowed}')"
            )
    elif dialect == "sqlite":
        for table, columns in IMMUTABLE_COLUMNS.items():
            comparison = " OR ".join(f"OLD.{column} IS NOT NEW.{column}" for column in columns)
            op.execute(
                f"CREATE TRIGGER guard_{table}_payload BEFORE UPDATE ON {table} "
                f"WHEN {comparison} BEGIN "
                f"SELECT RAISE(ABORT, '{table} payload is immutable; create a new revision'); END"
            )
    else:
        raise RuntimeError(f"Unsupported database dialect: {dialect}")


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    for table in IMMUTABLE_COLUMNS:
        suffix = f" ON {table}" if dialect == "postgresql" else ""
        op.execute(f"DROP TRIGGER IF EXISTS guard_{table}_payload{suffix}")
    if dialect == "postgresql":
        op.execute("DROP FUNCTION IF EXISTS career_guard_immutable_payload()")
