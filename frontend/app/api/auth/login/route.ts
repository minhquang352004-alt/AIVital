import { NextResponse } from "next/server";
import { createAuthSession, findUserByEmail, validateEmail, verifyPassword } from "../_auth";

export async function POST(request: Request) {
  const body = (await request.json().catch(() => ({}))) as { email?: unknown; password?: unknown };
  const email = typeof body.email === "string" ? body.email.trim() : "";
  const password = typeof body.password === "string" ? body.password : "";
  const user = validateEmail(email) ? await findUserByEmail(email) : null;
  if (!user || !(await verifyPassword(password, user.password_hash))) return NextResponse.json({ error: "Email hoặc mật khẩu không đúng" }, { status: 401 });
  await createAuthSession(user.id);
  return NextResponse.json({ user: { id: user.id, email: user.email, display_name: user.display_name } });
}
