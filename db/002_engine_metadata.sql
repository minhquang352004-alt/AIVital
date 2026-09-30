-- ============================================================
-- AIVitals - Engine Metadata / Validation / Audit Migration
-- Migration: 002
-- Requires: 001_week2_camera_demo.sql
-- PostgreSQL 15+
-- ============================================================


-- ============================================================
-- 1. rPPG METHODS
-- Theo dõi thuật toán rPPG được sử dụng:
-- GREEN / CHROM / POS / Deep Model...
-- ============================================================

CREATE TABLE IF NOT EXISTS rppg_methods (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    name TEXT NOT NULL,
    version TEXT NOT NULL,

    description TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_rppg_method_name_version
        UNIQUE (name, version)
);


-- ============================================================
-- 2. MODEL VERSIONS
-- Theo dõi version của model/engine.
-- Ví dụ: HR estimator, RR estimator, PhysNet...
-- ============================================================

CREATE TABLE IF NOT EXISTS model_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    name TEXT NOT NULL,
    version TEXT NOT NULL,

    model_type TEXT NOT NULL,

    checksum TEXT,
    metadata JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_model_name_version
        UNIQUE (name, version)
);


-- ============================================================
-- 3. CONSENTS
-- Tách consent thành bảng riêng để lưu lịch sử consent.
-- sessions hiện vẫn giữ consent_accepted và
-- consent_policy_version để tương thích migration 001.
-- ============================================================

CREATE TABLE IF NOT EXISTS consents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id UUID
        REFERENCES users(id)
        ON DELETE SET NULL,

    session_id UUID
        REFERENCES sessions(id)
        ON DELETE CASCADE,

    policy_version TEXT NOT NULL,

    accepted BOOLEAN NOT NULL,

    accepted_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT chk_consent_accepted_at
        CHECK (
            accepted = FALSE
            OR accepted_at IS NOT NULL
        )
);


-- ============================================================
-- 4. VALIDATIONS
-- Lưu kết quả validation của measurement.
-- Một measurement có thể được validate nhiều lần.
-- ============================================================

CREATE TABLE IF NOT EXISTS validations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    measurement_id UUID NOT NULL
        REFERENCES measurements(id)
        ON DELETE CASCADE,

    status TEXT NOT NULL
        CHECK (
            status IN (
                'OK',
                'BAD',
                'INVALID'
            )
        ),

    reason TEXT,

    validator_version TEXT,

    details JSONB,

    validated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- ============================================================
-- 5. AUDIT LOGS
-- Theo dõi các action quan trọng của hệ thống.
-- Ví dụ:
-- SESSION_CREATED
-- MEASUREMENT_STARTED
-- MEASUREMENT_STOPPED
-- RESULT_CREATED
-- ============================================================

CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id UUID
        REFERENCES users(id)
        ON DELETE SET NULL,

    session_id UUID
        REFERENCES sessions(id)
        ON DELETE SET NULL,

    measurement_id UUID
        REFERENCES measurements(id)
        ON DELETE SET NULL,

    action TEXT NOT NULL,

    entity_type TEXT,

    entity_id UUID,

    details JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- ============================================================
-- 6. LINK VITAL MEASUREMENT → rPPG METHOD / MODEL VERSION
-- Bổ sung traceability cho bảng vital_measurements hiện tại.
-- ============================================================

ALTER TABLE vital_measurements
    ADD COLUMN IF NOT EXISTS rppg_method_id UUID
        REFERENCES rppg_methods(id)
        ON DELETE SET NULL;

ALTER TABLE vital_measurements
    ADD COLUMN IF NOT EXISTS model_version_id UUID
        REFERENCES model_versions(id)
        ON DELETE SET NULL;

ALTER TABLE vital_measurements
    ADD COLUMN IF NOT EXISTS confidence NUMERIC(5,4)
        CHECK (
            confidence IS NULL
            OR confidence BETWEEN 0 AND 1
        );


-- ============================================================
-- 7. INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS
    idx_consents_session
ON consents(session_id);

CREATE INDEX IF NOT EXISTS
    idx_consents_user
ON consents(user_id);

CREATE INDEX IF NOT EXISTS
    idx_validations_measurement
ON validations(measurement_id, validated_at DESC);

CREATE INDEX IF NOT EXISTS
    idx_audit_logs_session
ON audit_logs(session_id, created_at DESC);

CREATE INDEX IF NOT EXISTS
    idx_audit_logs_measurement
ON audit_logs(measurement_id, created_at DESC);

CREATE INDEX IF NOT EXISTS
    idx_vital_measurements_rppg
ON vital_measurements(rppg_method_id);

CREATE INDEX IF NOT EXISTS
    idx_vital_measurements_model
ON vital_measurements(model_version_id);


-- ============================================================
-- 8. INITIAL rPPG METHODS
-- Seed các thuật toán của AIVitals.
-- ============================================================

INSERT INTO rppg_methods (
    name,
    version,
    description
)
VALUES

(
    'GREEN',
    '1.0',
    'Green channel rPPG baseline'
),

(
    'CHROM',
    '1.0',
    'Chrominance-based rPPG method'
),

(
    'POS',
    '1.0',
    'Plane-Orthogonal-to-Skin rPPG method'
)

ON CONFLICT (name, version)
DO NOTHING;