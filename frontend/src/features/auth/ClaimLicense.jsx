import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { KeyRound, Loader2, LogOut, ShoppingBag, Ban } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { AuthShell } from "./GoogleLogin";

export const ClaimLicense = ({ user, license, renewUrl, onClaimed, onLogout }) => {
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const revoked = license?.status === "revoked";

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setError("");
    try { await api.claim(code.trim()); onClaimed(); }
    catch (err) { setError(errMsg(err, "Gagal mengaktifkan kode")); }
    finally { setBusy(false); }
  };

  return (
    <AuthShell>
      <div data-testid="claim-license-page">
        <p className="text-xs text-slate-500">Masuk sebagai <span data-testid="claim-user-email" className="text-slate-300">{user.email}</span></p>
        {revoked ? (
          <div data-testid="license-revoked-notice" className="mt-3 rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
            <p className="flex items-center gap-2 font-semibold"><Ban className="h-4 w-4" /> Lisensi akun ini dicabut</p>
            <p className="mt-1 text-xs">Hubungi admin SAMPE untuk info lebih lanjut.</p>
          </div>
        ) : (<>
          <div className="mt-3 grid place-items-center h-12 w-12 rounded-xl bg-emerald-500/10 border border-emerald-500/30"><KeyRound className="h-6 w-6 text-emerald-400" /></div>
          <h2 className="mt-4 text-2xl font-extrabold tracking-tight">Aktifkan Lisensi</h2>
          <p className="mt-1 text-sm text-slate-400">Belum ada lisensi untuk Gmail ini. Kalau email di Lynk berbeda, masukkan kode lisensi dari halaman aktivasi.</p>
        </>)}
      </div>
      {!revoked && (
        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="claim-code">Kode Lisensi</Label>
            <Input id="claim-code" data-testid="claim-code-input" value={code} autoComplete="off" onChange={(e) => setCode(e.target.value.toUpperCase())}
              placeholder="SAMPE-XXXX-XXXX-XXXX" className="num h-12 tracking-wider bg-slate-900/60 border-slate-700" />
          </div>
          {error && <p data-testid="claim-error" className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">{error}</p>}
          <Button data-testid="claim-submit" type="submit" disabled={busy || code.trim().length < 4} className="w-full h-11 bg-emerald-500 hover:bg-emerald-600 text-slate-950 font-semibold">
            {busy && <Loader2 className="h-4 w-4 mr-2 animate-spin" />} Aktifkan
          </Button>
          <p className="text-xs text-slate-500">Lupa kode? Cari di <a href="/aktivasi" data-testid="claim-activation-link" className="text-emerald-400 hover:underline">halaman aktivasi</a> pakai email & Ref ID Lynk.</p>
        </form>
      )}
      <div className="flex flex-wrap gap-2">
        {renewUrl && !revoked && (
          <a data-testid="claim-buy-link" href={renewUrl} target="_blank" rel="noreferrer"
            className="inline-flex items-center gap-1.5 rounded-lg border border-amber-500/40 px-3 py-2 text-xs font-semibold text-amber-300 hover:bg-amber-500/10">
            <ShoppingBag className="h-4 w-4" /> Beli lisensi di Lynk.id
          </a>
        )}
        <button data-testid="claim-logout" onClick={onLogout} className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300 hover:bg-slate-800">
          <LogOut className="h-4 w-4" /> Ganti akun
        </button>
      </div>
    </AuthShell>
  );
};
