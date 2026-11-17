"""One APPROVED claim per found report, enforced by the database.

Revision ID: 0002_one_approved_claim
"""
from alembic import op

revision = '0002_one_approved_claim'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_claims_one_approved_per_found "
               "ON public.claims (found_report_id) WHERE status = 'APPROVED'")


def downgrade():
    op.execute('DROP INDEX IF EXISTS public.uq_claims_one_approved_per_found')
