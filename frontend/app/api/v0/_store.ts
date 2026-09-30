import { Pool, type QueryResultRow } from "pg";

export type MeasurementRecord = {
  id: string;
  session_id: string;
  status: "CREATED" | "RUNNING" | "COMPLETED" | "STOPPED" | "FAILED";
  state: string;
  heart_rate: number | null;
  respiration_rate: number | null;
  hrv_rmssd: number | null;
  quality_score: number | null;
  updated_at: string;
};

type SessionInput = {
  userId: string;
  consent?: { accepted?: boolean; policy_version?: string };
  client_version?: string;
  timezone?: string;
};

type MeasurementInput = {
  device?: { user_agent?: string; platform?: string; camera_facing?: "user" | "environment" };
  capture?: { fps?: number; width?: number; height?: number };
};

const globalForDb = globalThis as typeof globalThis & { aivitalsPool?: Pool };

function getPool() {
  if (!process.env.DATABASE_URL) {
    throw new Error("DATABASE_URL is required for PostgreSQL runtime");
  }
  globalForDb.aivitalsPool ??= new Pool({
    connectionString: process.env.DATABASE_URL,
    max: Number(process.env.DB_POOL_MAX ?? 10),
    idleTimeoutMillis: 30_000,
    connectionTimeoutMillis: 5_000
  });
  return globalForDb.aivitalsPool;
}

async function query<T extends QueryResultRow>(text: string, values: unknown[] = []) {
  return (await getPool().query<T>(text, values)).rows;
}

export async function checkDatabase() {
  await query<{ connected: number }>("SELECT 1 AS connected");
}

export async function createSession(input: SessionInput) {
  const client = await getPool().connect();
  try {
    await client.query("BEGIN");
    const sessionRows = await client.query<{
      id: string; status: string; created_at: string; expires_at: string;
    }>(
      `INSERT INTO sessions (user_id, status, consent_accepted, consent_policy_version, client_version, timezone, expires_at)
       VALUES ($1, 'CREATED', $2, $3, $4, $5, now() + interval '30 minutes')
       RETURNING id, status, created_at, expires_at`,
      [input.userId, input.consent?.accepted === true, input.consent?.policy_version ?? "2026-09-01", input.client_version ?? null, input.timezone ?? null]
    );
    const session = sessionRows.rows[0];
    await client.query(
      `INSERT INTO consents (session_id, policy_version, accepted, accepted_at)
       VALUES ($1, $2, $3, CASE WHEN $3 THEN now() ELSE NULL END)`,
      [session.id, input.consent?.policy_version ?? "2026-09-01", input.consent?.accepted === true]
    );
    await client.query("INSERT INTO audit_logs (session_id, action, entity_type, entity_id) VALUES ($1, 'SESSION_CREATED', 'session', $1)", [session.id]);
    await client.query("COMMIT");
    return session;
  } catch (error) {
    await client.query("ROLLBACK");
    throw error;
  } finally {
    client.release();
  }
}

export async function createMeasurement(sessionId: string, userId: string, input: MeasurementInput) {
  const client = await getPool().connect();
  try {
    await client.query("BEGIN");
    const session = await client.query<{ id: string }>("SELECT id FROM sessions WHERE id = $1 AND user_id = $2 FOR UPDATE", [sessionId, userId]);
    if (!session.rowCount) {
      await client.query("ROLLBACK");
      return null;
    }
    const measurement = await client.query<MeasurementRecord>(
      `INSERT INTO measurements (session_id, status, state)
       VALUES ($1, 'RUNNING', 'CAMERA_READY')
       RETURNING id, session_id, status, state, NULL::numeric AS heart_rate,
                 NULL::numeric AS respiration_rate, NULL::numeric AS hrv_rmssd,
                 NULL::numeric AS quality_score, started_at AS updated_at`,
      [sessionId]
    );
    const row = measurement.rows[0];
    const camera = input.device ?? {};
    const capture = input.capture ?? {};
    await client.query(
      `INSERT INTO cameras (session_id, facing, device_label, user_agent, platform, width, height, fps, permission_status)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'granted')`,
      [sessionId, camera.camera_facing ?? "user", null, camera.user_agent ?? null, camera.platform ?? null, capture.width ?? null, capture.height ?? null, capture.fps ?? null]
    );
    await client.query("UPDATE sessions SET status = 'ACTIVE' WHERE id = $1", [sessionId]);
    await client.query("INSERT INTO audit_logs (session_id, measurement_id, action, entity_type, entity_id) VALUES ($1, $2, 'MEASUREMENT_STARTED', 'measurement', $2)", [sessionId, row.id]);
    await client.query("COMMIT");
    return row;
  } catch (error) {
    await client.query("ROLLBACK");
    throw error;
  } finally {
    client.release();
  }
}

const measurementSelect = `SELECT m.id, m.session_id, m.status, m.state,
  v.heart_rate, v.respiration_rate, v.hrv_rmssd, v.quality_score,
  COALESCE(m.completed_at, m.stopped_at, m.started_at) AS updated_at
  FROM measurements m
  LEFT JOIN LATERAL (SELECT heart_rate, respiration_rate, hrv_rmssd, quality_score
    FROM vital_measurements WHERE measurement_id = m.id ORDER BY measured_at DESC LIMIT 1) v ON true`;

export async function getMeasurement(sessionId: string, measurementId: string) {
  const rows = await query<MeasurementRecord>(`${measurementSelect} JOIN sessions s ON s.id = m.session_id WHERE m.session_id = $1 AND m.id = $2`, [sessionId, measurementId]);
  return rows[0] ?? null;
}

export async function getMeasurementForUser(sessionId: string, measurementId: string, userId: string) {
  const rows = await query<{ id: string }>(
    "SELECT m.id FROM measurements m JOIN sessions s ON s.id = m.session_id WHERE m.session_id = $1 AND m.id = $2 AND s.user_id = $3",
    [sessionId, measurementId, userId]
  );
  return rows[0] ?? null;
}

export async function updateMeasurement(sessionId: string, measurementId: string, patch: Partial<MeasurementRecord>) {
  const client = await getPool().connect();
  try {
    await client.query("BEGIN");
    const current = await client.query<{ id: string }>("SELECT id FROM measurements WHERE session_id = $1 AND id = $2 FOR UPDATE", [sessionId, measurementId]);
    if (!current.rowCount) {
      await client.query("ROLLBACK");
      return null;
    }
    const status = patch.status ?? null;
    const state = patch.state ?? null;
    await client.query(
      `UPDATE measurements SET
       status = COALESCE($3, status),
       state = COALESCE($4, state),
       stopped_at = CASE WHEN $3 IN ('STOPPED', 'FAILED') THEN COALESCE(stopped_at, now()) ELSE stopped_at END,
       completed_at = CASE WHEN $3 = 'COMPLETED' THEN COALESCE(completed_at, now()) ELSE completed_at END
       WHERE session_id = $1 AND id = $2`,
      [sessionId, measurementId, status, state]
    );
    if (patch.heart_rate !== undefined || patch.respiration_rate !== undefined || patch.hrv_rmssd !== undefined || patch.quality_score !== undefined) {
      await client.query(
        `INSERT INTO vital_measurements (measurement_id, heart_rate, respiration_rate, hrv_rmssd, quality_score, algorithm_version)
         VALUES ($1, $2, $3, $4, $5, 'rppg-v1')`,
        [measurementId, patch.heart_rate ?? null, patch.respiration_rate ?? null, patch.hrv_rmssd ?? null, patch.quality_score ?? null]
      );
    }
    if (status === "COMPLETED" || status === "STOPPED" || status === "FAILED") {
      await client.query("UPDATE sessions SET status = 'COMPLETED' WHERE id = $1", [sessionId]);
    }
    const action = `MEASUREMENT_${status ?? "UPDATED"}`;
    await client.query("INSERT INTO audit_logs (session_id, measurement_id, action, entity_type, entity_id, details) VALUES ($1, $2, $3, 'measurement', $2, $4::jsonb)", [sessionId, measurementId, action, JSON.stringify({ status: status ?? "UPDATED" })]);
    await client.query("COMMIT");
    return getMeasurement(sessionId, measurementId);
  } catch (error) {
    await client.query("ROLLBACK");
    throw error;
  } finally {
    client.release();
  }
}

export async function listMeasurements(userId: string) {
  return query<MeasurementRecord>(`${measurementSelect} JOIN sessions s ON s.id = m.session_id WHERE m.status = 'COMPLETED' AND s.user_id = $1 ORDER BY updated_at DESC`, [userId]);
}
