import { NextResponse } from "next/server";
import { revokeAuthSession } from "../_auth";

export async function POST() {
  await revokeAuthSession();
  return NextResponse.json({ ok: true });
}
