"""
SQLAlchemy declarative base shared by the ORM models.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base declarative class cho toàn bộ models."""
    pass
