import { NextResponse } from "next/server";
import { getAuthenticatedUser } from "../../auth/_auth";
import { listMeasurements } from "../_store";

export async function GET() {
  const user = await getAuthenticatedUser();
  if (!user) return NextResponse.json({ error: "Unauthenticated" }, { status: 401 });
  const items = await listMeasurements(user.id);
  return NextResponse.json({ items, page: 1, page_size: items.length, total: items.length, has_next: false });
}
