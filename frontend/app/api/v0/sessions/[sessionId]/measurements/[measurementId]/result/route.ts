import { NextResponse } from "next/server";
import { getAuthenticatedUser } from "../../../../../../auth/_auth";
import { getMeasurement, getMeasurementForUser } from "../../../../../_store";

export async function GET(_request: Request, context: { params: Promise<{ sessionId: string; measurementId: string }> }) {
  const { sessionId, measurementId } = await context.params;
  const user = await getAuthenticatedUser();
  if (!user) return NextResponse.json({ error: "Unauthenticated" }, { status: 401 });
  if (!await getMeasurementForUser(sessionId, measurementId, user.id)) return NextResponse.json({ error: { code: "MEASUREMENT_NOT_FOUND", message: "Measurement was not found" } }, { status: 404 });
  const measurement = await getMeasurement(sessionId, measurementId);
  if (!measurement) return NextResponse.json({ error: { code: "MEASUREMENT_NOT_FOUND", message: "Measurement was not found" } }, { status: 404 });
  if (measurement.status !== "COMPLETED") return NextResponse.json({ result: { measurement_id: measurement.id, status: "PENDING" } });
  return NextResponse.json({
    result: {
      measurement_id: measurement.id,
      status: "READY",
      quality: (measurement.quality_score ?? 0) >= 80 ? "GOOD" : "LOW",
      quality_score: measurement.quality_score,
      measured_at: measurement.updated_at,
      metrics: {
        heart_rate: { value: measurement.heart_rate, unit: "bpm" },
        hrv_rmssd: { value: measurement.hrv_rmssd, unit: "ms" },
        respiration_rate: { value: measurement.respiration_rate, unit: "breaths_per_minute" }
      },
      algorithm_version: "rppg-v1"
    }
  });
}
