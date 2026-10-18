"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { LoadingState, ErrorState } from "@/components/ui";
import { useAuth } from "@/components/AuthGate";

const input = "mt-1 w-full bg-panelraised border border-border rounded-sm px-2 py-2 text-xs text-ink outline-none";

export default function UsersPage() {
  const { enabled, user } = useAuth();
  const [users, setUsers] = useState<any[]>([]);
  const [roles, setRoles] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ username: "", password: "", role: "analyst", display_name: "" });

  async function load() {
    try {
      const d = await api.listUsers();
      setUsers(d.users || []);
      setRoles(d.roles || []);
      setError(null);
    } catch (e: any) {
      setError(String(e?.message || "").includes("403") ? "Only administrators can manage users." : e.message || "Could not load users.");
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { load(); }, []);

  async function create() {
    try {
      await api.createUser(form);
      setForm({ username: "", password: "", role: "analyst", display_name: "" });
      await load();
    } catch (e: any) { setError(e.message || "Could not create user."); }
  }

  async function update(username: string, body: Record<string, unknown>) {
    try { await api.updateUser(username, body); await load(); }
    catch (e: any) { setError(e.message || "Could not update user."); }
  }

  if (loading) return <LoadingState label="Loading users" />;

  return (
    <div className="max-w-[1000px]">
      <h1 className="text-lg text-ink font-medium">Users and roles</h1>
      <p className="text-xs text-muted mt-1">
        Analyst: read only. Scout: also edits shortlists and notes. Director: also edits the club profile. Admin: everything, including users and the audit log.
      </p>
      {!enabled && <p className="text-2xs text-faint mt-2">Login is currently switched off on the server, so roles are not enforced.</p>}
      {error && <div className="mt-4"><ErrorState message={error} /></div>}

      <section className="border border-border bg-panel rounded-sm p-4 mt-5">
        <h2 className="text-sm text-ink font-medium">Add user</h2>
        <div className="grid grid-cols-1 md:grid-cols-5 gap-3 mt-3">
          <label className="text-2xs text-faint">Username<input value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} className={input} /></label>
          <label className="text-2xs text-faint">Display name<input value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} className={input} /></label>
          <label className="text-2xs text-faint">Password (10+ chars)<input type="password" autoComplete="new-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className={input} /></label>
          <label className="text-2xs text-faint">Role
            <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} className={input}>
              {roles.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </label>
          <div className="flex items-end">
            <button onClick={create} disabled={!form.username || !form.password} className="px-4 py-2 text-xs rounded-sm bg-accent text-black font-medium disabled:opacity-40">Create</button>
          </div>
        </div>
      </section>

      <section className="border border-border bg-panel rounded-sm mt-5 overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-faint text-left border-b border-border">
              <th className="px-4 py-2 font-normal">User</th><th className="px-4 py-2 font-normal">Role</th>
              <th className="px-4 py-2 font-normal">Status</th><th className="px-4 py-2 font-normal">Last sign-in</th><th className="px-4 py-2 font-normal" />
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.username} className="border-b border-border last:border-0">
                <td className="px-4 py-2 text-ink">{u.display_name || u.username}<div className="text-2xs text-faint">{u.username}</div></td>
                <td className="px-4 py-2">
                  <select value={u.role} onChange={(e) => update(u.username, { role: e.target.value })} aria-label={`Role for ${u.username}`}
                    className="bg-panelraised border border-border rounded-sm px-2 py-1 text-xs text-ink">
                    {roles.map((r) => <option key={r} value={r}>{r}</option>)}
                  </select>
                </td>
                <td className="px-4 py-2 text-muted">{u.is_active ? "Active" : "Disabled"}</td>
                <td className="px-4 py-2 text-muted tabular">{u.last_login_at ? u.last_login_at.slice(0, 16).replace("T", " ") : "Never"}</td>
                <td className="px-4 py-2 text-right whitespace-nowrap">
                  <button onClick={() => update(u.username, { is_active: !u.is_active })} disabled={u.username === user?.username}
                    className="text-2xs text-muted hover:text-ink underline mr-3 disabled:opacity-40">{u.is_active ? "Disable" : "Enable"}</button>
                  <button onClick={() => { const pw = window.prompt(`New password for ${u.username} (10+ characters)`); if (pw) update(u.username, { password: pw }); }}
                    className="text-2xs text-muted hover:text-ink underline">Reset password</button>
                </td>
              </tr>
            ))}
            {users.length === 0 && <tr><td colSpan={5} className="px-4 py-6 text-center text-faint">No users yet.</td></tr>}
          </tbody>
        </table>
      </section>
    </div>
  );
}
