import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_database_url_must_be_configured(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
