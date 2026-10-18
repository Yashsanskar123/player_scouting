"use client";

import { useEffect, useState } from "react";
import { api, setToken } from "@/lib/api";

export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [enabled, setEnabled] = useState<boolean | null>(null);

  useEffect(() => {
    api.authStatus().then((s: any) => {
      setEnabled(!!s.auth_enabled);
      if (!s.auth_enabled) window.location.replace("/");
    }).catch(() => setEnabled(true));
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api.login(username, password);
      setToken(res.access_token);
      window.location.assign("/"); // full reload so every page loads with the new session
    } catch (err: any) {
      const msg = String(err?.message || "");
      setError(msg.includes("429") ? "Too many attempts. Please wait a few minutes and try again."
        : msg.includes("401") ? "Incorrect username or password."
        : "Could not sign in. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  if (enabled === null) return <div className="p-6 text-sm text-muted">Loading…</div>;

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <form onSubmit={submit} className="w-full max-w-sm border border-border bg-panel rounded-sm p-6">
        <div className="text-ink font-semibold tracking-tight text-lg">ScoutIQ</div>
        <div className="text-faint text-2xs mt-0.5 mb-5">Recruitment Intelligence</div>
        <label className="block text-2xs text-faint">
          Username
          <input autoFocus autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)}
            className="mt-1 w-full bg-panelraised border border-border rounded-sm px-2 py-2 text-sm text-ink outline-none" />
        </label>
        <label className="block text-2xs text-faint mt-3">
          Password
          <input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full bg-panelraised border border-border rounded-sm px-2 py-2 text-sm text-ink outline-none" />
        </label>
        {error && <div role="alert" className="mt-3 text-xs text-riskhigh">{error}</div>}
        <button type="submit" disabled={busy || !username || !password}
          className="mt-5 w-full px-4 py-2 text-sm rounded-sm bg-accent text-black font-medium disabled:opacity-40">
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
