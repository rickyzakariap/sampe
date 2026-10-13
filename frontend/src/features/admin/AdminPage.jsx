import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Toaster } from "@/components/ui/sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2, ShieldCheck, LogOut } from "lucide-react";
import { adminApi, errMsg, ADMIN_TOKEN_KEY } from "@/lib/api";
import { LicenseTable } from "./LicenseTable";
import { CreateLicenseForm } from "./CreateLicenseForm";
import { LynkSettings, OrdersTable } from "./LynkSettings";

const AdminLogin = ({ onLogin }) => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setError("");
    try { onLogin((await adminApi.login(email, password)).token); }
    catch (err) { setError(errMsg(err, "Gagal masuk")); }
    finally { setBusy(false); }
  };
  return (
    <div data-testid="admin-login-page" className="min-h-screen grid place-items-center bg-background p-6">
      <form onSubmit={submit} className="w-full max-w-sm space-y-5 rounded-2xl border border-slate-800 bg-[#161F30] p-8 animate-fade-up">
        <div className="flex items-center gap-2 text-amber-400"><ShieldCheck className="h-5 w-5" /><span className="text-xs font-semibold uppercase tracking-widest">Admin Panel</span></div>
        <h1 className="text-2xl font-extrabold tracking-tight">Kelola Lisensi</h1>
        <div className="space-y-2"><Label>Email</Label><Input data-testid="admin-email-input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="bg-slate-900 border-slate-700" /></div>
        <div className="space-y-2"><Label>Password</Label><Input data-testid="admin-password-input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="bg-slate-900 border-slate-700" /></div>
        {error && <p data-testid="admin-login-error" className="text-sm text-red-400">{error}</p>}
        <Button data-testid="admin-login-submit" type="submit" disabled={busy || !email || !password} className="w-full bg-amber-500 hover:bg-amber-600 text-slate-950 font-semibold">
          {busy && <Loader2 className="h-4 w-4 mr-2 animate-spin" />} Masuk
        </Button>
      </form>
    </div>
  );
};

const AdminDashboard = ({ admin, onLogout }) => {
  const [rows, setRows] = useState(null);
  const load = useCallback(async () => { try { setRows(await adminApi.list()); } catch (e) { toast.error(errMsg(e)); } }, []);
  useEffect(() => { load(); }, [load]);

  const act = async (fn, okMsg) => {
    try { await fn(); toast.success(okMsg); await load(); } catch (e) { toast.error(errMsg(e)); }
  };

  const counts = (rows || []).reduce((a, r) => ({ ...a, [r.status]: (a[r.status] || 0) + 1 }), {});
  return (
    <div data-testid="admin-dashboard" className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-40 border-b border-slate-800 bg-slate-950/80 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6">
          <div className="flex items-center gap-2"><ShieldCheck className="h-5 w-5 text-amber-400" /><p className="font-heading font-extrabold">SAMPE · Admin</p></div>
          <div className="flex items-center gap-3 text-sm text-slate-400">
            <span className="hidden sm:inline">{admin.email}</span>
            <Button data-testid="admin-logout" size="sm" variant="outline" className="border-slate-700" onClick={onLogout}><LogOut className="h-4 w-4 mr-1" /> Keluar</Button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl space-y-6 px-4 py-8 sm:px-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-amber-400">Manajemen Lisensi</p>
            <h1 className="text-3xl font-extrabold tracking-tight">Daftar User & Lisensi</h1>
          </div>
          <div className="flex gap-2 text-xs num">
            {[["active", "Aktif", "text-emerald-400"], ["unused", "Belum dipakai", "text-sky-400"], ["expired", "Habis", "text-amber-400"], ["revoked", "Dicabut", "text-red-400"]].map(([k, l, c]) => (
              <span key={k} data-testid={`admin-count-${k}`} className="rounded-lg border border-slate-800 bg-[#161F30] px-3 py-2"><span className={`font-bold ${c}`}>{counts[k] || 0}</span> {l}</span>
            ))}
          </div>
        </div>
        <LynkSettings />
        <CreateLicenseForm onCreated={load} />
        {rows === null ? <Loader2 className="h-6 w-6 animate-spin text-amber-400" /> : (
          <LicenseTable rows={rows}
            onExtend={(r, days) => act(() => adminApi.extend(r.id, days), `Lisensi ${r.label} diperpanjang ${days} hari`)}
            onRevoke={(r) => act(() => adminApi.revoke(r.id), `Lisensi ${r.label} dicabut`)}
            onRestore={(r) => act(() => adminApi.restore(r.id), `Lisensi ${r.label} dipulihkan`)} />
        )}
        <OrdersTable refreshKey={rows} />
      </main>
    </div>
  );
};

export default function AdminPage() {
  const [admin, setAdmin] = useState(undefined);
  const check = useCallback(async () => {
    if (!localStorage.getItem(ADMIN_TOKEN_KEY)) return setAdmin(null);
    try { setAdmin(await adminApi.me()); } catch { setAdmin(null); }
  }, []);
  useEffect(() => { check(); }, [check]);
  useEffect(() => {
    const out = () => setAdmin(null);
    window.addEventListener("pulse:admin-logout", out);
    return () => window.removeEventListener("pulse:admin-logout", out);
  }, []);
  const logout = () => { localStorage.removeItem(ADMIN_TOKEN_KEY); setAdmin(null); };

  return (
    <>
      {admin === undefined ? <div className="min-h-screen grid place-items-center bg-background"><Loader2 className="h-8 w-8 animate-spin text-amber-400" /></div>
        : admin ? <AdminDashboard admin={admin} onLogout={logout} />
        : <AdminLogin onLogin={(t) => { localStorage.setItem(ADMIN_TOKEN_KEY, t); check(); }} />}
      <Toaster position="top-center" richColors />
    </>
  );
}
