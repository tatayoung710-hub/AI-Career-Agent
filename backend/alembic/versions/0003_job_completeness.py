"""Separate job leads from complete job descriptions.

Revision ID: 0003
Revises: 0002
"""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "jobs", sa.Column("jd_complete", sa.Boolean(), nullable=False, server_default=sa.true())
    )
    op.execute("UPDATE jobs SET jd_complete = FALSE WHERE jd_text LIKE '%原表格未提供完整 JD%'")


def downgrade() -> None:
    # Supported by PostgreSQL and the SQLite versions bundled with Python >= 3.12.
    # Avoid rebuilding a parent table referenced by immutable job versions.
    op.drop_column("jobs", "jd_complete")
