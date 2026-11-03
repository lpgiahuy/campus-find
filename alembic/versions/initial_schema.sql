BEGIN;

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS public.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(320) NOT NULL,
    password_hash TEXT NOT NULL,
    full_name VARCHAR(150) NOT NULL,
    role VARCHAR(10) NOT NULL DEFAULT 'USER',
    contact_phone VARCHAR(25),
    allow_contact_sharing BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_users_role CHECK (role IN ('ADMIN', 'USER')),
    CONSTRAINT ck_users_email_nonempty CHECK (length(btrim(email)) > 0),
    CONSTRAINT ck_users_name_nonempty CHECK (length(btrim(full_name)) > 0),
    CONSTRAINT ck_users_password_nonempty CHECK (length(password_hash) > 0)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email_lower ON public.users (lower(email));
CREATE INDEX IF NOT EXISTS ix_users_role_active ON public.users (role, is_active);

CREATE TABLE IF NOT EXISTS public.categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT ck_categories_name_nonempty CHECK (length(btrim(name)) > 0)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_categories_name_lower
    ON public.categories (lower(name));

CREATE TABLE IF NOT EXISTS public.locations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(150) NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT ck_locations_name_nonempty CHECK (length(btrim(name)) > 0)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_locations_name_lower
    ON public.locations (lower(name));

CREATE TABLE IF NOT EXISTS public.lost_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    category_id UUID NOT NULL,
    location_id UUID NOT NULL,
    item_name VARCHAR(200) NOT NULL,
    color VARCHAR(50),
    lost_at TIMESTAMPTZ NOT NULL,
    description_public TEXT,
    private_identifiers TEXT,
    status VARCHAR(12) NOT NULL DEFAULT 'OPEN',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_lost_user
        FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE RESTRICT,
    CONSTRAINT fk_lost_category
        FOREIGN KEY (category_id) REFERENCES public.categories(id) ON DELETE RESTRICT,
    CONSTRAINT fk_lost_location
        FOREIGN KEY (location_id) REFERENCES public.locations(id) ON DELETE RESTRICT,
    CONSTRAINT ck_lost_status
        CHECK (status IN ('OPEN', 'RESOLVED', 'CLOSED')),
    CONSTRAINT ck_lost_item_nonempty
        CHECK (length(btrim(item_name)) > 0)
);
CREATE INDEX IF NOT EXISTS ix_lost_user_status
    ON public.lost_reports (user_id, status);
CREATE INDEX IF NOT EXISTS ix_lost_candidates
    ON public.lost_reports (category_id, status, lost_at DESC);
CREATE INDEX IF NOT EXISTS ix_lost_location
    ON public.lost_reports (location_id);

CREATE TABLE IF NOT EXISTS public.found_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    category_id UUID NOT NULL,
    location_id UUID NOT NULL,
    item_name VARCHAR(200) NOT NULL,
    color VARCHAR(50),
    found_at TIMESTAMPTZ NOT NULL,
    description_public TEXT,
    private_identifiers TEXT,
    storage_note TEXT,
    status VARCHAR(12) NOT NULL DEFAULT 'OPEN',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_found_user
        FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE RESTRICT,
    CONSTRAINT fk_found_category
        FOREIGN KEY (category_id) REFERENCES public.categories(id) ON DELETE RESTRICT,
    CONSTRAINT fk_found_location
        FOREIGN KEY (location_id) REFERENCES public.locations(id) ON DELETE RESTRICT,
    CONSTRAINT ck_found_status
        CHECK (status IN ('OPEN', 'RETURNED', 'CLOSED')),
    CONSTRAINT ck_found_item_nonempty
        CHECK (length(btrim(item_name)) > 0)
);
CREATE INDEX IF NOT EXISTS ix_found_user_status
    ON public.found_reports (user_id, status);
CREATE INDEX IF NOT EXISTS ix_found_candidates
    ON public.found_reports (category_id, status, found_at DESC);
CREATE INDEX IF NOT EXISTS ix_found_location
    ON public.found_reports (location_id);

CREATE TABLE IF NOT EXISTS public.matches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lost_report_id UUID NOT NULL,
    found_report_id UUID NOT NULL,
    score NUMERIC(5,2) NOT NULL,
    score_breakdown JSONB NOT NULL DEFAULT '{}'::jsonb,
    algorithm_version VARCHAR(50) NOT NULL DEFAULT 'rules-v1',
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    lost_notified_at TIMESTAMPTZ,
    found_notified_at TIMESTAMPTZ,
    lost_seen_at TIMESTAMPTZ,
    found_seen_at TIMESTAMPTZ,
    CONSTRAINT fk_match_lost
        FOREIGN KEY (lost_report_id) REFERENCES public.lost_reports(id) ON DELETE RESTRICT,
    CONSTRAINT fk_match_found
        FOREIGN KEY (found_report_id) REFERENCES public.found_reports(id) ON DELETE RESTRICT,
    CONSTRAINT uq_match_lost_found
        UNIQUE (lost_report_id, found_report_id),
    CONSTRAINT ck_match_score
        CHECK (score >= 0 AND score <= 100),
    CONSTRAINT ck_match_breakdown_object
        CHECK (jsonb_typeof(score_breakdown) = 'object'),
    CONSTRAINT ck_match_algorithm_nonempty
        CHECK (length(btrim(algorithm_version)) > 0)
);
CREATE INDEX IF NOT EXISTS ix_matches_lost_score
    ON public.matches (lost_report_id, score DESC);
CREATE INDEX IF NOT EXISTS ix_matches_found_score
    ON public.matches (found_report_id, score DESC);
CREATE INDEX IF NOT EXISTS ix_matches_calculated_at
    ON public.matches (calculated_at DESC);

CREATE TABLE IF NOT EXISTS public.claims (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    found_report_id UUID NOT NULL,
    lost_report_id UUID NULL,
    claimant_id UUID NOT NULL,
    reviewed_by UUID NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    reason TEXT NOT NULL,
    review_note TEXT,
    claimant_contact_consent BOOLEAN NOT NULL DEFAULT FALSE,
    finder_contact_consent BOOLEAN NOT NULL DEFAULT FALSE,
    contact_shared_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_claim_found
        FOREIGN KEY (found_report_id) REFERENCES public.found_reports(id) ON DELETE RESTRICT,
    CONSTRAINT fk_claim_lost
        FOREIGN KEY (lost_report_id) REFERENCES public.lost_reports(id) ON DELETE RESTRICT,
    CONSTRAINT fk_claim_claimant
        FOREIGN KEY (claimant_id) REFERENCES public.users(id) ON DELETE RESTRICT,
    CONSTRAINT fk_claim_reviewer
        FOREIGN KEY (reviewed_by) REFERENCES public.users(id) ON DELETE RESTRICT,
    CONSTRAINT ck_claim_status CHECK (
        status IN (
            'PENDING', 'UNDER_REVIEW', 'APPROVED', 'REJECTED',
            'WITHDRAWN', 'CANCELLED', 'COMPLETED'
        )
    ),
    CONSTRAINT ck_claim_reason_nonempty
        CHECK (length(btrim(reason)) > 0),
    CONSTRAINT ck_claim_reviewed_required CHECK (
        status NOT IN ('APPROVED', 'REJECTED', 'COMPLETED')
        OR reviewed_by IS NOT NULL
    ),
    CONSTRAINT uq_claim_claimant_found
        UNIQUE (claimant_id, found_report_id)
);
CREATE INDEX IF NOT EXISTS ix_claims_found_status
    ON public.claims (found_report_id, status);
CREATE INDEX IF NOT EXISTS ix_claims_lost
    ON public.claims (lost_report_id) WHERE lost_report_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_claims_claimant_created
    ON public.claims (claimant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_claims_reviewer
    ON public.claims (reviewed_by) WHERE reviewed_by IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_claims_status_created
    ON public.claims (status, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS uq_claims_one_completed_per_found
    ON public.claims (found_report_id)
    WHERE status = 'COMPLETED';

CREATE TABLE IF NOT EXISTS public.claim_evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_id UUID NOT NULL,
    evidence_text TEXT NOT NULL,
    file_reference TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_evidence_claim
        FOREIGN KEY (claim_id) REFERENCES public.claims(id) ON DELETE RESTRICT,
    CONSTRAINT ck_evidence_text_nonempty
        CHECK (length(btrim(evidence_text)) > 0)
);
CREATE INDEX IF NOT EXISTS ix_evidence_claim_created
    ON public.claim_evidence (claim_id, created_at DESC);

CREATE TABLE IF NOT EXISTS public.handover_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_id UUID NOT NULL UNIQUE,
    verified_by UUID NOT NULL,
    handed_over_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    method VARCHAR(20) NOT NULL,
    confirmation_note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_handover_claim
        FOREIGN KEY (claim_id) REFERENCES public.claims(id) ON DELETE RESTRICT,
    CONSTRAINT fk_handover_verifier
        FOREIGN KEY (verified_by) REFERENCES public.users(id) ON DELETE RESTRICT,
    CONSTRAINT ck_handover_method
        CHECK (method IN ('IN_PERSON', 'ADMIN_ASSISTED'))
);
CREATE INDEX IF NOT EXISTS ix_handover_verified_by_date
    ON public.handover_records (verified_by, handed_over_at DESC);

CREATE OR REPLACE FUNCTION public.campusfind_touch_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS tr_users_touch_updated_at ON public.users;
CREATE TRIGGER tr_users_touch_updated_at
    BEFORE UPDATE ON public.users
    FOR EACH ROW EXECUTE FUNCTION public.campusfind_touch_updated_at();

DROP TRIGGER IF EXISTS tr_lost_touch_updated_at ON public.lost_reports;
CREATE TRIGGER tr_lost_touch_updated_at
    BEFORE UPDATE ON public.lost_reports
    FOR EACH ROW EXECUTE FUNCTION public.campusfind_touch_updated_at();

DROP TRIGGER IF EXISTS tr_found_touch_updated_at ON public.found_reports;
CREATE TRIGGER tr_found_touch_updated_at
    BEFORE UPDATE ON public.found_reports
    FOR EACH ROW EXECUTE FUNCTION public.campusfind_touch_updated_at();

DROP TRIGGER IF EXISTS tr_claims_touch_updated_at ON public.claims;
CREATE TRIGGER tr_claims_touch_updated_at
    BEFORE UPDATE ON public.claims
    FOR EACH ROW EXECUTE FUNCTION public.campusfind_touch_updated_at();

CREATE OR REPLACE FUNCTION public.campusfind_validate_claim()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_finder_id UUID;
    v_lost_owner_id UUID;
BEGIN
    SELECT user_id INTO v_finder_id
    FROM public.found_reports
    WHERE id = NEW.found_report_id;

    IF v_finder_id IS NOT NULL AND v_finder_id = NEW.claimant_id THEN
        RAISE EXCEPTION 'A user cannot claim their own found report'
            USING ERRCODE = '23514';
    END IF;

    IF NEW.lost_report_id IS NOT NULL THEN
        SELECT user_id INTO v_lost_owner_id
        FROM public.lost_reports
        WHERE id = NEW.lost_report_id;

        IF v_lost_owner_id IS NOT NULL AND v_lost_owner_id <> NEW.claimant_id THEN
            RAISE EXCEPTION 'The referenced lost report must belong to the claimant'
                USING ERRCODE = '23514';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS tr_claims_validate ON public.claims;
CREATE TRIGGER tr_claims_validate
    BEFORE INSERT OR UPDATE OF found_report_id, lost_report_id, claimant_id
    ON public.claims
    FOR EACH ROW EXECUTE FUNCTION public.campusfind_validate_claim();

CREATE OR REPLACE FUNCTION public.campusfind_validate_handover()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_found_id UUID;
    v_claim_status VARCHAR(20);
    v_found_status VARCHAR(12);
    v_verifier_is_admin BOOLEAN;
BEGIN
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION 'Handover records are immutable; create a correction workflow'
            USING ERRCODE = '23514';
    END IF;

    SELECT found_report_id, status
      INTO v_found_id, v_claim_status
      FROM public.claims
     WHERE id = NEW.claim_id;

    IF v_found_id IS NULL THEN
        RAISE EXCEPTION 'Claim does not exist'
            USING ERRCODE = '23503';
    END IF;

    IF v_claim_status <> 'APPROVED' THEN
        RAISE EXCEPTION 'Only APPROVED claims can be handed over'
            USING ERRCODE = '23514';
    END IF;

    SELECT (role = 'ADMIN' AND is_active)
      INTO v_verifier_is_admin
      FROM public.users
     WHERE id = NEW.verified_by;

    IF v_verifier_is_admin IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'Handover verifier must be an active ADMIN'
            USING ERRCODE = '23514';
    END IF;

    SELECT status INTO v_found_status
      FROM public.found_reports
     WHERE id = v_found_id
     FOR UPDATE;

    IF v_found_status <> 'OPEN' THEN
        RAISE EXCEPTION 'Found report is not open for handover'
            USING ERRCODE = '23514';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM public.handover_records h
        JOIN public.claims c ON c.id = h.claim_id
        WHERE c.found_report_id = v_found_id
    ) THEN
        RAISE EXCEPTION 'This found report already has a handover'
            USING ERRCODE = '23505';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS tr_handover_validate ON public.handover_records;
CREATE TRIGGER tr_handover_validate
    BEFORE INSERT OR UPDATE ON public.handover_records
    FOR EACH ROW EXECUTE FUNCTION public.campusfind_validate_handover();

COMMIT;
