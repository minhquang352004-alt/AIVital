import { NextResponse } from "next/server";
import { getAuthenticatedUser } from "../../auth/_auth";
import { createSession } from "../_store";

export async function POST(request: Request) {
  const body = (await request.json().catch(() => ({}))) as {
    consent?: { accepted?: boolean; policy_version?: string };
  };
  if (!body.consent?.accepted) {
    return NextResponse.json({ error: { code: "CONSENT_REQUIRED", message: "Consent is required" } }, { status: 422 });
  }
  const user = await getAuthenticatedUser();
  if (!user) return NextResponse.json({ error: "Unauthenticated" }, { status: 401 });
  const session = await createSession({ ...body, userId: user.id });
  return NextResponse.json({ session: { id: session.id, status: session.status, created_at: session.created_at, expires_at: session.expires_at } }, { status: 201 });
}
