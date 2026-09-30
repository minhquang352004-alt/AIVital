import { NextResponse } from "next/server";
import { checkDatabase } from "../../v0/_store";

export async function GET() {
  try {
    await checkDatabase();
    return NextResponse.json({ database: "connected" });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Database connection failed";
    return NextResponse.json({ database: "disconnected", error: message }, { status: 503 });
  }
}
