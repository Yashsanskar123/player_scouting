"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import CoverageNotice from "@/components/CoverageNotice";
import DataFreshness from "@/components/DataFreshness";
import { api, clearToken } from "@/lib/api";

type AuthState = { enabled: boolean; user: any | null; logout: () => void };
const AuthContext = createContext<AuthState>({ enabled: false, user: null, logout: () => {} });
export const useAuth = () => useContext(AuthContext);

/**
 * App shell + sign-in gate. When login is switched off on the server (default) this renders
 * the normal shell with no change. When it is on, signed-out visitors are sent to /login.
 */
export default function AuthGate({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [ready, setReady] = useState(false);
  const [enabled, setEnabled] = useState(false);
  const [user, setUser] = useState<any | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const status = await api.authStatus();
        if (!status.auth_enabled) { if (alive) { setEnabled(false); setReady(true); } return; }
        try {
          const me = await api.me();
          if (!alive) return;
          if (me.authenticated) { setEnabled(true); setUser(me.user); setReady(true); return; }
        } catch { /* fall through to sign-in */ }
        clearToken();
        if (alive) { setEnabled(true); setReady(true); }
        if (window.location.pathname !== "/login") window.location.replace("/login");
      } catch {
        // Status endpoint unreachable: show the shell; pages display their own API errors.
        if (alive) { setEnabled(false); setReady(true); }
      }
    })();
    return () => { alive = false; };
  }, []);

  function logout() {
    clearToken();
    window.location.replace("/login");
  }

  if (pathname === "/login") return <>{children}</>;
  if (!ready) return <div className="p-6 text-sm text-muted">Loading…</div>;
  if (enabled && !user) return null; // redirecting to /login

  return (
    <AuthContext.Provider value={{ enabled, user, logout }}>
      <div className="flex">
        <Sidebar />
        <main className="flex-1 min-w-0 px-8 py-7 max-w-[1400px]">
          <CoverageNotice />
          {children}
          <DataFreshness />
        </main>
      </div>
    </AuthContext.Provider>
  );
}
