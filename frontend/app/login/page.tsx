"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const data = new FormData(event.currentTarget);
    const response = await fetch("/api/auth/login", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ email: data.get("email"), password: data.get("password") }) });
    const payload = (await response.json()) as { error?: string };
    if (!response.ok) setError(payload.error ?? "Không thể đăng nhập");
    else router.push("/");
    setBusy(false);
  }
  return <main className="auth-page"><form className="auth-card" onSubmit={submit}><span className="eyebrow">AIVITALS</span><h1>Đăng nhập</h1><label>Email<input name="email" type="email" required autoComplete="email" /></label><label>Mật khẩu<input name="password" type="password" required autoComplete="current-password" /></label>{error && <p className="auth-error">{error}</p>}<button className="primary-button full" disabled={busy}>{busy ? "Đang đăng nhập..." : "Đăng nhập"} <span>→</span></button><button className="secondary-button" type="button" onClick={() => router.push("/register")}>Chưa có tài khoản? Đăng ký</button></form></main>;
}
