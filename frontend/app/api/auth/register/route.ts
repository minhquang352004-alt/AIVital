import { NextResponse } from "next/server";
import { createAuthSession, registerUser, validateEmail } from "../_auth";

export async function POST(request: Request) {
  const body = (await request.json().catch(() => ({}))) as { email?: unknown; password?: unknown; display_name?: unknown };
  const email = typeof body.email === "string" ? body.email.trim().toLowerCase() : "";
  const password = typeof body.password === "string" ? body.password : "";
  if (!validateEmail(email)) return NextResponse.json({ error: "Email không hợp lệ" }, { status: 400 });
  if (password.length < 8) return NextResponse.json({ error: "Mật khẩu phải có ít nhất 8 ký tự" }, { status: 400 });
  try {
    const user = await registerUser(email, password, typeof body.display_name === "string" ? body.display_name : null);
    await createAuthSession(user.id);
    return NextResponse.json({ user }, { status: 201 });
  } catch (error) {
    if (error instanceof Error && error.message.includes("duplicate key")) return NextResponse.json({ error: "Email đã tồn tại" }, { status: 409 });
    throw error;
  }
}
