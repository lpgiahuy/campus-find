from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from app.db.base import Base


def uuid_pk():
    return Column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))


def timestamp():
    return Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class User(Base):
    __tablename__ = 'users'
    id = uuid_pk()
    email = Column(String(320), nullable=False)
    password_hash = Column(Text, nullable=False)
    full_name = Column(String(150), nullable=False)
    role = Column(String(10), nullable=False, server_default='USER')
    contact_phone = Column(String(25))
    allow_contact_sharing = Column(Boolean, nullable=False, server_default=text('false'))
    is_active = Column(Boolean, nullable=False, server_default=text('true'))
    created_at = timestamp()
    updated_at = timestamp()
    __table_args__ = (CheckConstraint("role IN ('ADMIN', 'USER')", name='ck_users_role'), CheckConstraint('length(btrim(email)) > 0', name='ck_users_email_nonempty'), CheckConstraint('length(btrim(full_name)) > 0', name='ck_users_name_nonempty'), CheckConstraint('length(password_hash) > 0', name='ck_users_password_nonempty'), Index('uq_users_email_lower', func.lower(email), unique=True), Index('ix_users_role_active', 'role', 'is_active'))


class Category(Base):
    __tablename__ = 'categories'
    id = uuid_pk()
    name = Column(String(100), nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, nullable=False, server_default=text('true'))
    __table_args__ = (CheckConstraint('length(btrim(name)) > 0', name='ck_categories_name_nonempty'), Index('uq_categories_name_lower', func.lower(name), unique=True))


class Location(Base):
    __tablename__ = 'locations'
    id = uuid_pk()
    name = Column(String(150), nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, nullable=False, server_default=text('true'))
    __table_args__ = (CheckConstraint('length(btrim(name)) > 0', name='ck_locations_name_nonempty'), Index('uq_locations_name_lower', func.lower(name), unique=True))


class LostReport(Base):
    __tablename__ = 'lost_reports'
    id = uuid_pk()
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='RESTRICT', name='fk_lost_user'), nullable=False)
    category_id = Column(UUID(as_uuid=True), ForeignKey('categories.id', ondelete='RESTRICT', name='fk_lost_category'), nullable=False)
    location_id = Column(UUID(as_uuid=True), ForeignKey('locations.id', ondelete='RESTRICT', name='fk_lost_location'), nullable=False)
    item_name = Column(String(200), nullable=False)
    color = Column(String(50))
    lost_at = Column(DateTime(timezone=True), nullable=False)
    description_public = Column(Text)
    private_identifiers = Column(Text)
    status = Column(String(12), nullable=False, server_default='OPEN')
    created_at = timestamp()
    updated_at = timestamp()
    __table_args__ = (CheckConstraint("status IN ('OPEN', 'RESOLVED', 'CLOSED')", name='ck_lost_status'), CheckConstraint('length(btrim(item_name)) > 0', name='ck_lost_item_nonempty'), Index('ix_lost_user_status', 'user_id', 'status'), Index('ix_lost_candidates', category_id, status, lost_at.desc()), Index('ix_lost_location', 'location_id'))


class FoundReport(Base):
    __tablename__ = 'found_reports'
    id = uuid_pk()
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='RESTRICT', name='fk_found_user'), nullable=False)
    category_id = Column(UUID(as_uuid=True), ForeignKey('categories.id', ondelete='RESTRICT', name='fk_found_category'), nullable=False)
    location_id = Column(UUID(as_uuid=True), ForeignKey('locations.id', ondelete='RESTRICT', name='fk_found_location'), nullable=False)
    item_name = Column(String(200), nullable=False)
    color = Column(String(50))
    found_at = Column(DateTime(timezone=True), nullable=False)
    description_public = Column(Text)
    private_identifiers = Column(Text)
    storage_note = Column(Text)
    status = Column(String(12), nullable=False, server_default='OPEN')
    created_at = timestamp()
    updated_at = timestamp()
    __table_args__ = (CheckConstraint("status IN ('OPEN', 'RETURNED', 'CLOSED')", name='ck_found_status'), CheckConstraint('length(btrim(item_name)) > 0', name='ck_found_item_nonempty'), Index('ix_found_user_status', 'user_id', 'status'), Index('ix_found_candidates', category_id, status, found_at.desc()), Index('ix_found_location', 'location_id'))


class Match(Base):
    __tablename__ = 'matches'
    id = uuid_pk()
    lost_report_id = Column(UUID(as_uuid=True), ForeignKey('lost_reports.id', ondelete='RESTRICT', name='fk_match_lost'), nullable=False)
    found_report_id = Column(UUID(as_uuid=True), ForeignKey('found_reports.id', ondelete='RESTRICT', name='fk_match_found'), nullable=False)
    score = Column(Numeric(5, 2), nullable=False)
    score_breakdown = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    algorithm_version = Column(String(50), nullable=False, server_default='rules-v1')
    calculated_at = timestamp()
    lost_notified_at = Column(DateTime(timezone=True))
    found_notified_at = Column(DateTime(timezone=True))
    lost_seen_at = Column(DateTime(timezone=True))
    found_seen_at = Column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint('lost_report_id', 'found_report_id', name='uq_match_lost_found'), CheckConstraint('score >= 0 AND score <= 100', name='ck_match_score'), CheckConstraint("jsonb_typeof(score_breakdown) = 'object'", name='ck_match_breakdown_object'), CheckConstraint('length(btrim(algorithm_version)) > 0', name='ck_match_algorithm_nonempty'), Index('ix_matches_lost_score', lost_report_id, score.desc()), Index('ix_matches_found_score', found_report_id, score.desc()), Index('ix_matches_calculated_at', calculated_at.desc()))


class Claim(Base):
    __tablename__ = 'claims'
    id = uuid_pk()
    found_report_id = Column(UUID(as_uuid=True), ForeignKey('found_reports.id', ondelete='RESTRICT', name='fk_claim_found'), nullable=False)
    lost_report_id = Column(UUID(as_uuid=True), ForeignKey('lost_reports.id', ondelete='RESTRICT', name='fk_claim_lost'))
    claimant_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='RESTRICT', name='fk_claim_claimant'), nullable=False)
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='RESTRICT', name='fk_claim_reviewer'))
    status = Column(String(20), nullable=False, server_default='PENDING')
    reason = Column(Text, nullable=False)
    review_note = Column(Text)
    claimant_contact_consent = Column(Boolean, nullable=False, server_default=text('false'))
    finder_contact_consent = Column(Boolean, nullable=False, server_default=text('false'))
    contact_shared_at = Column(DateTime(timezone=True))
    created_at = timestamp()
    updated_at = timestamp()
    __table_args__ = (CheckConstraint("status IN ('PENDING', 'UNDER_REVIEW', 'APPROVED', 'REJECTED', 'WITHDRAWN', 'CANCELLED', 'COMPLETED')", name='ck_claim_status'), CheckConstraint('length(btrim(reason)) > 0', name='ck_claim_reason_nonempty'), CheckConstraint("status NOT IN ('APPROVED', 'REJECTED', 'COMPLETED') OR reviewed_by IS NOT NULL", name='ck_claim_reviewed_required'), UniqueConstraint('claimant_id', 'found_report_id', name='uq_claim_claimant_found'), Index('ix_claims_found_status', 'found_report_id', 'status'), Index('ix_claims_lost', lost_report_id, postgresql_where=lost_report_id.is_not(None)), Index('ix_claims_claimant_created', claimant_id, created_at.desc()), Index('ix_claims_reviewer', reviewed_by, postgresql_where=reviewed_by.is_not(None)), Index('ix_claims_status_created', status, created_at.desc()), Index('uq_claims_one_completed_per_found', found_report_id, unique=True, postgresql_where=text("status = 'COMPLETED'")))


class ClaimEvidence(Base):
    __tablename__ = 'claim_evidence'
    id = uuid_pk()
    claim_id = Column(UUID(as_uuid=True), ForeignKey('claims.id', ondelete='RESTRICT', name='fk_evidence_claim'), nullable=False)
    evidence_text = Column(Text, nullable=False)
    file_reference = Column(Text)
    created_at = timestamp()
    __table_args__ = (CheckConstraint('length(btrim(evidence_text)) > 0', name='ck_evidence_text_nonempty'), Index('ix_evidence_claim_created', claim_id, created_at.desc()))


class HandoverRecord(Base):
    __tablename__ = 'handover_records'
    id = uuid_pk()
    claim_id = Column(UUID(as_uuid=True), ForeignKey('claims.id', ondelete='RESTRICT', name='fk_handover_claim'), nullable=False, unique=True)
    verified_by = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='RESTRICT', name='fk_handover_verifier'), nullable=False)
    handed_over_at = timestamp()
    method = Column(String(20), nullable=False)
    confirmation_note = Column(Text)
    created_at = timestamp()
    __table_args__ = (CheckConstraint("method IN ('IN_PERSON', 'ADMIN_ASSISTED')", name='ck_handover_method'), Index('ix_handover_verified_by_date', verified_by, handed_over_at.desc()))
