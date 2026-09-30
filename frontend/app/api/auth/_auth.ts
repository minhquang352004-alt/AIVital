import { createHash, randomBytes } from "crypto";
import bcrypt from "bcryptjs";
import { cookies } from "next/headers";
import { Pool, type QueryResultRow } from "pg";

const COOKIE_NAME = "aivitals_session";
const SESSION_DAYS = 7;
const globalForDb = globalThis as typeof globalThis & { aivitalsPool?: Pool };

function pool() {
  if (!process.env.DATABASE_URL) throw new Error("DATABASE_URL is required for PostgreSQL runtime");
  globalForDb.aivitalsPool ??= new Pool({ connectionString: process.env.DATABASE_URL, max: Number(process.env.DB_POOL_MAX ?? 10) });
  return globalForDb.aivitalsPool;
}

function hashToken(token: string) {
  return createHash("sha256").update(token).digest("hex");
}

export function validateEmail(email: unknown) {
  return typeof email === "string" && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
}

export async function createAuthSession(userId: string) {
  const token = randomBytes(32).toString("hex");
  await pool().query(
    "INSERT INTO auth_sessions (user_id, token_hash, expires_at) VALUES ($1, $2, now() + interval '7 days')",
    [userId, hashToken(token)]
  );
  (await cookies()).set(COOKIE_NAME, token, { httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "lax", path: "/", maxAge: SESSION_DAYS * 24 * 60 * 60 });
}

export async function getAuthenticatedUser() {
  const token = (await cookies()).get(COOKIE_NAME)?.value;
  if (!token) return null;
  const result = await pool().query<{ id: string; email: string; display_name: string | null }>(
    `SELECT u.id, u.email, u.display_name
     FROM auth_sessions a JOIN users u ON u.id = a.user_id
     WHERE a.token_hash = $1 AND a.revoked_at IS NULL AND a.expires_at > now()`,
    [hashToken(token)]
  );
  return result.rows[0] ?? null;
}

export async function revokeAuthSession() {
  const cookieStore = await cookies();
  const token = cookieStore.get(COOKIE_NAME)?.value;
  if (token) await pool().query("UPDATE auth_sessions SET revoked_at = now() WHERE token_hash = $1 AND revoked_at IS NULL", [hashToken(token)]);
  cookieStore.set(COOKIE_NAME, "", { httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "lax", path: "/", maxAge: 0 });
}

export async function findUserByEmail(email: string) {
  const result = await pool().query<{ id: string; email: string; password_hash: string; display_name: string | null }>(
    "SELECT id, email, password_hash, display_name FROM users WHERE lower(email) = lower($1)",
    [email.trim()]
  );
  return result.rows[0] ?? null;
}

export async function registerUser(email: string, password: string, displayName: string | null) {
  const passwordHash = await bcrypt.hash(password, 12);
  const result = await pool().query<{ id: string; email: string; display_name: string | null }>(
    `INSERT INTO users (email, password_hash, display_name) VALUES ($1, $2, $3)
     RETURNING id, email, display_name`,
    [email.trim().toLowerCase(), passwordHash, displayName?.trim() || null]
  );
  return result.rows[0];
}

export async function verifyPassword(password: string, passwordHash: string) {
  return bcrypt.compare(password, passwordHash);
}

export async function authQuery<T extends QueryResultRow>(text: string, values: unknown[] = []) {
  return (await pool().query<T>(text, values)).rows;
}
