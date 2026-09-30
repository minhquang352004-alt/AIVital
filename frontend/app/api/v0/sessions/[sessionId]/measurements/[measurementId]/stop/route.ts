import { NextResponse } from "next/server";
import { getAuthenticatedUser } from "../../../../../../auth/_auth";
import { getMeasurementForUser, updateMeasurement } from "../../../../../_store";

export async function POST(request: Request, context: { params: Promise<{ sessionId: string; measurementId: string }> }) {
  const { sessionId, measurementId } = await context.params;
  const user = await getAuthenticatedUser();
  if (!user) return NextResponse.json({ error: "Unauthenticated" }, { status: 401 });
  if (!await getMeasurementForUser(sessionId, measurementId, user.id)) return NextResponse.json({ error: { code: "MEASUREMENT_NOT_FOUND", message: "Measurement was not found" } }, { status: 404 });
  const body = (await request.json().catch(() => ({}))) as { reason?: string };
  const measurement = await updateMeasurement(sessionId, measurementId, {
    status: "STOPPED",
    state: "IDLE"
  });
  if (!measurement) return NextResponse.json({ error: { code: "MEASUREMENT_NOT_FOUND", message: "Measurement was not found" } }, { status: 404 });
  void body;
  return NextResponse.json({ measurement });
}
