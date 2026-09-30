"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

export default function RegisterPage() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const data = new FormData(event.currentTarget);
    const response = await fetch("/api/auth/register", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ email: data.get("email"), password: data.get("password"), display_name: data.get("display_name") }) });
    const payload = (await response.json()) as { error?: string };
    if (!response.ok) setError(payload.error ?? "Không thể đăng ký");
    else router.push("/");
    setBusy(false);
  }
  return <main className="auth-page"><form className="auth-card" onSubmit={submit}><span className="eyebrow">AIVITALS</span><h1>Tạo tài khoản</h1><label>Tên hiển thị<input name="display_name" autoComplete="name" /></label><label>Email<input name="email" type="email" required autoComplete="email" /></label><label>Mật khẩu<input name="password" type="password" minLength={8} required autoComplete="new-password" /></label>{error && <p className="auth-error">{error}</p>}<button className="primary-button full" disabled={busy}>{busy ? "Đang tạo..." : "Đăng ký"} <span>→</span></button><button className="secondary-button" type="button" onClick={() => router.push("/login")}>Đã có tài khoản? Đăng nhập</button></form></main>;
}
