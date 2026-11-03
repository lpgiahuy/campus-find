"""Run only against an explicitly supplied, empty PostgreSQL test database."""
import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

TEST_URL = os.getenv('TEST_DATABASE_URL')


@pytest.mark.skipif(not TEST_URL, reason='Set TEST_DATABASE_URL to a dedicated empty PostgreSQL database')
def test_initial_migration(monkeypatch):
    engine = create_engine(TEST_URL.replace('postgresql+asyncpg://', 'postgresql+psycopg2://'))
    try:
        assert not inspect(engine).get_table_names(), 'Test database must be empty'
        monkeypatch.setenv('DATABASE_URL', TEST_URL)
        monkeypatch.delenv('SYNC_DATABASE_URL', raising=False)
        from app.core.config import settings
        monkeypatch.setattr(settings, 'DATABASE_URL', TEST_URL)
        monkeypatch.setattr(settings, 'SYNC_DATABASE_URL', None)
        command.upgrade(Config('alembic.ini'), 'head')
        expected = {'users', 'categories', 'locations', 'lost_reports', 'found_reports',
                    'matches', 'claims', 'claim_evidence', 'handover_records'}
        assert set(inspect(engine).get_table_names()) == expected | {'alembic_version'}
        with engine.connect() as conn:
            assert conn.scalar(text('select count(*) from pg_trigger where not tgisinternal and tgname like :name'), {'name': 'tr_%'}) >= 6
            assert conn.scalar(text('select version_num from alembic_version')) == '0001_initial'
    finally:
        engine.dispose()
