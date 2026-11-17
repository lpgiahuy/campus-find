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


class ClaimStatus(StrEnum):
    PENDING = "PENDING"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class HandoverMethod(StrEnum):  # khớp ck_handover_method
    IN_PERSON = "IN_PERSON"
    ADMIN_ASSISTED = "ADMIN_ASSISTED"


class MatchLevel(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
