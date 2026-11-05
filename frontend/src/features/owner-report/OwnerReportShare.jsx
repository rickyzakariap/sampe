import { useEffect, useState } from "react";
import { Link2 } from "lucide-react";
import { api, errMsg } from "@/lib/api";

const copy = async (value) => navigator.clipboard.writeText(value);

export function OwnerReportShare() {
  const [open, setOpen] = useState(false);
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    api.ownerReportManage().then(setReport).catch((e) => setError(errMsg(e, "Laporan belum dapat dimuat.")));
  }, [open]);

  const act = async (operation) => {
    setBusy(true); setError("");
    try { setReport(await operation()); }
    catch (e) { setError(errMsg(e, "Perubahan link gagal.")); }
    finally { setBusy(false); }
  };
  const link = report?.token ? `${window.location.origin}/report/${report.slug}-${report.token}` : "";

  return <section className="mb-5 rounded-xl border border-slate-800 bg-[#161F30] p-4" data-testid="owner-report-share">
    <button type="button" onClick={() => setOpen(!open)} className="flex items-center gap-2 text-sm font-semibold text-emerald-400">
      <Link2 className="h-4 w-4" /> Bagikan laporan Owner {open ? "−" : "+"}
    </button>
    {open && <div className="mt-4 space-y-3 text-sm">
      <p className="text-slate-400">Siapa pun yang memiliki link dapat membaca KPI toko. Bagikan hanya kepada penerima yang Anda percaya.</p>
      {error && <p role="alert" className="text-red-400">{error}</p>}
      {report?.enabled ? <>
        {link ? <>
          <div className="break-all rounded-lg bg-slate-900 p-3 text-slate-200">{link}</div>
          <button type="button" onClick={() => copy(link).catch(() => setError("Gagal menyalin link."))} className="rounded-lg border border-slate-700 px-3 py-2">Salin link</button>
        </> : <p className="text-amber-300">Link belum dapat ditampilkan. Muat ulang halaman atau hubungi admin.</p>}
        <div className="flex flex-wrap gap-2 border-t border-slate-800 pt-3">
          <button type="button" disabled={busy} onClick={() => window.confirm("Ganti link? Link lama langsung tidak berlaku.") && act(api.ownerReportRotate)} className="rounded-lg border border-amber-500/40 px-3 py-2 text-amber-300">Ganti link</button>
          <button type="button" disabled={busy} onClick={() => window.confirm("Cabut link laporan sekarang?") && act(api.ownerReportRevoke)} className="rounded-lg border border-red-500/40 px-3 py-2 text-red-300">Cabut link</button>
        </div>
      </> : report && <button type="button" disabled={busy} onClick={() => act(api.ownerReportCreate)} className="rounded-lg bg-emerald-500 px-3 py-2 font-semibold text-slate-950">Buat link laporan</button>}
    </div>}
  </section>;
}
