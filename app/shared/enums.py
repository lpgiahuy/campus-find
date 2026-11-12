"""Shared Enums (UserRole, ReportStatus, ClaimStatus, MatchLevel, HandoverMethod)."""

from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "ADMIN"
    USER = "USER"


class LostReportStatus(StrEnum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class FoundReportStatus(StrEnum):
    OPEN = "OPEN"
    RETURNED = "RETURNED"
    CLOSED = "CLOSED"


class MatchLevel(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
