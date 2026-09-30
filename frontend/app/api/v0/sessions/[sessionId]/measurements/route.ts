import { NextResponse } from "next/server";
import { getAuthenticatedUser } from "../../../../auth/_auth";
import { createMeasurement } from "../../../_store";

export async function POST(request: Request, context: { params: Promise<{ sessionId: string }> }) {
  const { sessionId } = await context.params;
  const user = await getAuthenticatedUser();
  if (!user) return NextResponse.json({ error: "Unauthenticated" }, { status: 401 });
  const input = (await request.json().catch(() => ({}))) as Record<string, unknown>;
  const measurement = await createMeasurement(sessionId, user.id, input);
  if (!measurement) return NextResponse.json({ error: { code: "SESSION_NOT_FOUND", message: "Session was not found" } }, { status: 404 });
  return NextResponse.json({ measurement }, { status: 201 });
}
