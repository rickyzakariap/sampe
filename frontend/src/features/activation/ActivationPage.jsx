import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2, Copy, CheckCircle2, Search } from "lucide-react";
import { toast } from "sonner";
import { Toaster } from "@/components/ui/sonner";
import { api, errMsg } from "@/lib/api";
import { AuthShell } from "@/features/auth/GoogleLogin";

const Result = ({ r }) => (
  <div data-testid="activation-result" className="space-y-4 rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-5">
    <p className="flex items-center gap-2 text-sm font-semibold text-emerald-300"><CheckCircle2 className="h-4 w-4" />
      {r.action === "extended" ? `Lisensi diperpanjang +${r.days} hari` : `Lisensi ${r.days} hari siap dipakai`}</p>
    <div>
      <p className="text-xs text-slate-400">Kode lisensi</p>
      <div className="mt-1 flex items-center justify-between gap-2">
        <p data-testid="activation-code" className="num text-lg font-bold tracking-wider text-white">{r.code}</p>
        <Button data-testid="activation-copy" size="sm" variant="outline" className="border-emerald-500/40 text-emerald-300"
          onClick={() => navigator.clipboard.writeText(r.code).then(() => toast.success("Kode disalin"))}><Copy className="h-4 w-4 mr-1" /> Salin</Button>
      </div>
      {r.expires_at && <p className="mt-1 text-xs text-slate-400">Aktif s/d {new Date(r.expires_at).toLocaleDateString("id-ID", { day: "2-digit", month: "long", year: "numeric" })}</p>}
      {!r.expires_at && <p className="mt-1 text-xs text-slate-400">Masa aktif {r.duration_days} hari dimulai saat pertama login.</p>}
    </div>
    <ol className="list-decimal space-y-1 pl-4 text-xs text-slate-300">
      <li>Klik <b>Masuk ke SAMPE</b> lalu pilih <b>Masuk dengan Google</b>.</li>
      <li>Pakai Gmail <b>{r.email}</b> agar lisensi langsung aktif otomatis.</li>
      <li>Kalau pakai Gmail lain, tempel kode di atas saat diminta.</li>
    </ol>
    <a href="/" data-testid="activation-go-login" className="block rounded-lg bg-emerald-500 py-2.5 text-center text-sm font-semibold text-slate-950 hover:bg-emerald-600">Masuk ke SAMPE</a>
  </div>
);

export default function ActivationPage() {
  const [email, setEmail] = useState("");
  const [ref, setRef] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setError(""); setResult(null);
    try { setResult(await api.activation(email.trim(), ref.trim())); }
    catch (err) { setError(errMsg(err, "Gagal mencari order")); }
    finally { setBusy(false); }
  };

  return (
    <AuthShell>
      <div data-testid="activation-page">
        <p className="text-xs font-semibold uppercase tracking-widest text-emerald-400">Aktivasi Lisensi</p>
        <h2 className="mt-2 text-2xl font-extrabold tracking-tight">Ambil kode lisensimu</h2>
        <p className="mt-1 text-sm text-slate-400">Masukkan email & Ref ID dari bukti pembayaran Lynk.id.</p>
      </div>
      {result ? <Result r={result} /> : (
        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-2"><Label>Email pembelian</Label>
            <Input data-testid="activation-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="nama@gmail.com" className="h-11 bg-slate-900/60 border-slate-700" /></div>
          <div className="space-y-2"><Label>Ref ID order Lynk</Label>
            <Input data-testid="activation-ref" value={ref} onChange={(e) => setRef(e.target.value)} placeholder="cth: LYNK-20260424-ABC123" className="num h-11 bg-slate-900/60 border-slate-700" /></div>
          {error && <p data-testid="activation-error" className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">{error}</p>}
          <Button data-testid="activation-submit" type="submit" disabled={busy || !email.trim() || ref.trim().length < 3} className="w-full h-11 bg-emerald-500 hover:bg-emerald-600 text-slate-950 font-semibold">
            {busy ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Search className="h-4 w-4 mr-2" />} Cari Lisensi
          </Button>
        </form>
      )}
      <Toaster position="top-center" richColors />
    </AuthShell>
  );
}
