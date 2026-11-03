"""Create the initial nine-table PostgreSQL schema.

Revision ID: 0001_initial
"""
from pathlib import Path
from alembic import op
from sqlalchemy import inspect

revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    if not op.get_context().as_sql:
        existing = set(inspect(op.get_bind()).get_table_names())
        tables = {'users', 'categories', 'locations', 'lost_reports', 'found_reports',
                  'matches', 'claims', 'claim_evidence', 'handover_records'}
        if existing & tables:
            raise RuntimeError('Existing CampusFind tables detected. Use an empty database for this migration.')
    sql = Path(__file__).with_name('initial_schema.sql').read_text(encoding='utf-8')
    sql = sql.removeprefix('BEGIN;').removesuffix('COMMIT;\n')
    op.execute(sql)


def downgrade():
    for table in ('handover_records', 'claim_evidence', 'claims', 'matches',
                  'found_reports', 'lost_reports', 'locations', 'categories', 'users'):
        op.drop_table(table)
    for function in ('campusfind_validate_handover', 'campusfind_validate_claim', 'campusfind_touch_updated_at'):
        op.execute(f'DROP FUNCTION IF EXISTS public.{function}()')
