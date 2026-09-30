import { NextResponse } from "next/server";
import { getAuthenticatedUser } from "../_auth";

export async function GET() {
  const user = await getAuthenticatedUser();
  if (!user) return NextResponse.json({ error: "Unauthenticated" }, { status: 401 });
  return NextResponse.json({ user });
}
