-- AIVitals Week 2 persistence contract.
-- PostgreSQL 15+. This stores metadata only; raw camera frames are not persisted.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_ref TEXT UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    status TEXT NOT NULL CHECK (status IN ('CREATED', 'ACTIVE', 'COMPLETED', 'CANCELLED', 'EXPIRED')),
    consent_accepted BOOLEAN NOT NULL,
    consent_policy_version TEXT NOT NULL,
    client_version TEXT,
    timezone TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS cameras (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    facing TEXT NOT NULL CHECK (facing IN ('user', 'environment')),
    device_label TEXT,
    user_agent TEXT,
    platform TEXT,
    width INTEGER CHECK (width IS NULL OR width > 0),
    height INTEGER CHECK (height IS NULL OR height > 0),
    fps NUMERIC(6, 2) CHECK (fps IS NULL OR fps > 0),
    permission_status TEXT NOT NULL CHECK (permission_status IN ('unknown', 'granted', 'denied', 'error')),
    error_code TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS measurements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    camera_id UUID REFERENCES cameras(id) ON DELETE SET NULL,
    status TEXT NOT NULL CHECK (status IN ('CREATED', 'RUNNING', 'STOPPED', 'COMPLETED', 'FAILED')),
    state TEXT NOT NULL CHECK (state IN (
        'IDLE', 'CAMERA_PERMISSION', 'CAMERA_READY', 'FACE_SEARCH',
        'FACE_LOCKED', 'SIGNAL_ACQUIRING', 'QUALITY_CHECK', 'COMPUTING', 'RESULT_READY'
    )),
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    stopped_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS face_quality (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    measurement_id UUID NOT NULL REFERENCES measurements(id) ON DELETE CASCADE,
    detected BOOLEAN NOT NULL,
    detection_confidence NUMERIC(5, 4) CHECK (detection_confidence IS NULL OR detection_confidence BETWEEN 0 AND 1),
    bbox_x INTEGER,
    bbox_y INTEGER,
    bbox_width INTEGER,
    bbox_height INTEGER,
    centered BOOLEAN,
    lighting_score NUMERIC(5, 2) CHECK (lighting_score IS NULL OR lighting_score BETWEEN 0 AND 100),
    quality_score NUMERIC(5, 2) CHECK (quality_score IS NULL OR quality_score BETWEEN 0 AND 100),
    captured_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Vital signs are stored separately from per-frame quality metadata so that
-- result/history queries do not need to scan the quality stream.
CREATE TABLE IF NOT EXISTS vital_measurements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    measurement_id UUID NOT NULL REFERENCES measurements(id) ON DELETE CASCADE,
    heart_rate NUMERIC(6, 2) CHECK (heart_rate IS NULL OR heart_rate > 0),
    respiration_rate NUMERIC(6, 2) CHECK (respiration_rate IS NULL OR respiration_rate > 0),
    hrv_rmssd NUMERIC(8, 2) CHECK (hrv_rmssd IS NULL OR hrv_rmssd >= 0),
    quality_score NUMERIC(5, 2) CHECK (quality_score IS NULL OR quality_score BETWEEN 0 AND 100),
    algorithm_version TEXT NOT NULL,
    measured_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS measurement_quality (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    measurement_id UUID NOT NULL REFERENCES measurements(id) ON DELETE CASCADE,
    bvp_sqi NUMERIC(5, 4) CHECK (bvp_sqi IS NULL OR bvp_sqi BETWEEN 0 AND 1),
    signal_status TEXT NOT NULL CHECK (signal_status IN ('BUFFERING', 'OK', 'LOW_QUALITY', 'FACE_LOST')),
    sample_count INTEGER NOT NULL CHECK (sample_count >= 0),
    captured_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_created ON sessions(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_measurements_session_started ON measurements(session_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_face_quality_measurement_captured ON face_quality(measurement_id, captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_vital_measurements_measurement_measured ON vital_measurements(measurement_id, measured_at DESC);
CREATE INDEX IF NOT EXISTS idx_measurement_quality_measurement_captured ON measurement_quality(measurement_id, captured_at DESC);
