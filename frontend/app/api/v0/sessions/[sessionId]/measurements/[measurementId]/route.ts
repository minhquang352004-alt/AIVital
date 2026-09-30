import { NextResponse } from "next/server";
import { getAuthenticatedUser } from "../../../../../auth/_auth";
import { getMeasurement, getMeasurementForUser, updateMeasurement, type MeasurementRecord } from "../../../../_store";

type Context = { params: Promise<{ sessionId: string; measurementId: string }> };

export async function GET(_request: Request, context: Context) {
  const { sessionId, measurementId } = await context.params;
  const user = await getAuthenticatedUser();
  if (!user) return NextResponse.json({ error: "Unauthenticated" }, { status: 401 });
  const owned = await getMeasurementForUser(sessionId, measurementId, user.id);
  if (!owned) return NextResponse.json({ error: { code: "MEASUREMENT_NOT_FOUND", message: "Measurement was not found" } }, { status: 404 });
  const measurement = await getMeasurement(sessionId, measurementId);
  if (!measurement) return NextResponse.json({ error: { code: "MEASUREMENT_NOT_FOUND", message: "Measurement was not found" } }, { status: 404 });
  return NextResponse.json({ measurement });
}

export async function PATCH(request: Request, context: Context) {
  const { sessionId, measurementId } = await context.params;
  const user = await getAuthenticatedUser();
  if (!user) return NextResponse.json({ error: "Unauthenticated" }, { status: 401 });
  const owned = await getMeasurementForUser(sessionId, measurementId, user.id);
  if (!owned) return NextResponse.json({ error: { code: "MEASUREMENT_NOT_FOUND", message: "Measurement was not found" } }, { status: 404 });
  const patch = (await request.json().catch(() => ({}))) as Partial<MeasurementRecord>;
  const measurement = await updateMeasurement(sessionId, measurementId, patch);
  if (!measurement) return NextResponse.json({ error: { code: "MEASUREMENT_NOT_FOUND", message: "Measurement was not found" } }, { status: 404 });
  return NextResponse.json({ measurement });
}
