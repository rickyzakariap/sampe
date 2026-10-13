import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Plus, Loader2, Copy } from "lucide-react";
import { adminApi, errMsg } from "@/lib/api";

export const DURATIONS = [[1, "1 hari"], [7, "7 hari"], [30, "30 hari"], [365, "365 hari"]];

export const copyText = async (text) => {
  try { await navigator.clipboard.writeText(text); toast.success("Kode disalin"); }
  catch { toast.error("Gagal menyalin, salin manual"); }
};

export const CreateLicenseForm = ({ onCreated }) => {
  const [label, setLabel] = useState("");
  const [email, setEmail] = useState("");
  const [days, setDays] = useState(30);
  const [busy, setBusy] = useState(false);
  const [created, setCreated] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const lic = await adminApi.create(label.trim(), days, email.trim());
      setEmail("");
      setCreated(lic); setLabel("");
      await onCreated();
    } catch (err) { toast.error(errMsg(err)); }
    finally { setBusy(false); }
  };

  return (
    <div className="rounded-xl border border-slate-800 bg-[#161F30] p-5">
      <form onSubmit={submit} className="flex flex-wrap items-end gap-4">
        <div className="space-y-1.5 flex-1 min-w-[220px]">
          <Label className="text-xs text-slate-400">Nama pemilik / toko</Label>
          <Input data-testid="admin-license-label" value={label} maxLength={80} onChange={(e) => setLabel(e.target.value)} placeholder="cth: Bu Rina – Toko Kain Rina" className="h-10 bg-slate-900 border-slate-700" />
        </div>
        <div className="space-y-1.5 min-w-[200px]">
          <Label className="text-xs text-slate-400">Gmail pembeli (opsional, auto-aktif saat login)</Label>
          <Input data-testid="admin-license-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="nama@gmail.com" className="h-10 bg-slate-900 border-slate-700" />
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs text-slate-400">Durasi</Label>
          <div className="flex gap-1 rounded-lg border border-slate-700 bg-slate-900 p-1">
            {DURATIONS.map(([d, l]) => (
              <button type="button" key={d} data-testid={`admin-duration-${d}`} onClick={() => setDays(d)}
                className={`rounded-md px-3 py-1.5 text-xs font-semibold transition-colors ${days === d ? "bg-amber-500 text-slate-950" : "text-slate-400 hover:text-white"}`}>{l}</button>
            ))}
          </div>
        </div>
        <Button data-testid="admin-create-license" type="submit" disabled={busy || !label.trim()} className="h-10 bg-amber-500 hover:bg-amber-600 text-slate-950 font-semibold">
          {busy ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Plus className="h-4 w-4 mr-1" />} Buat Lisensi
        </Button>
      </form>
      {created && (
        <div data-testid="admin-created-license" className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-emerald-500/30 bg-emerald-500/5 px-4 py-3">
          <div>
            <p className="text-xs text-slate-400">Lisensi baru untuk <span className="text-slate-200">{created.label}</span> · {created.duration_days} hari (mulai dihitung saat login pertama)</p>
            <p data-testid="admin-created-code" className="num mt-1 text-lg font-bold tracking-wider text-emerald-400">{created.code}</p>
          </div>
          <Button data-testid="admin-copy-created-code" size="sm" variant="outline" className="border-emerald-500/40 text-emerald-300" onClick={() => copyText(created.code)}>
            <Copy className="h-4 w-4 mr-1" /> Salin Kode
          </Button>
        </div>
      )}
    </div>
  );
};
