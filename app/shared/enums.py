"""Shared Enums (UserRole, ReportStatus, ClaimStatus, MatchLevel, HandoverMethod)."""
from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "ADMIN"
    USER = "USER"
