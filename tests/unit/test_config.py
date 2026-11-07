import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_database_url_must_be_configured(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_debug_parsing():
    s_off = Settings(
        DATABASE_URL="postgresql+asyncpg://u:p@localhost/db",
        JWT_SECRET_KEY="secret",
        DEBUG="off",
    )
    assert s_off.DEBUG is False

    s_on = Settings(
        DATABASE_URL="postgresql+asyncpg://u:p@localhost/db",
        JWT_SECRET_KEY="secret",
        DEBUG="on",
    )
    assert s_on.DEBUG is True

    with pytest.raises(ValidationError):
        Settings(
            DATABASE_URL="postgresql+asyncpg://u:p@localhost/db",
            JWT_SECRET_KEY="secret",
            DEBUG="random_unknown",
        )
