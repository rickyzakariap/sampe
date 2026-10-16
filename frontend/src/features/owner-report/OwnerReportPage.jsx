import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { RefreshCw } from "lucide-react";
import { Dashboard } from "@/components/Dashboard";
import { BrandMark } from "@/components/BrandLogo";
import { AiMarkdown } from "@/components/AiMarkdown";
import { ownerReportApi, errMsg } from "@/lib/api";
import { rupiahFull } from "@/lib/format";

const LABELS = {
  sales: "Penjualan", ads: "Ads", livestream: "Live Streaming",
  branding: "Branding", campaign: "Campaign", kol: "KOL",
};
const monthWib = () => new Intl.DateTimeFormat("en-CA", {
  timeZone: "Asia/Jakarta", year: "numeric", month: "2-digit",
}).format(new Date());
const stamp = (value) => new Date(value).toLocaleString("id-ID", { timeZone: "Asia/Jakarta" }) + " WIB";

export function OwnerReportPage() {
  const { shareId } = useParams();
  const [month, setMonth] = useState(monthWib());
  const [report, setReport] = useState(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [invalid, setInvalid] = useState(false);
  const busyRef = useRef(false);
  const loadedMonthRef = useRef(null);

  const load = useCallback(async (selectedMonth) => {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true); setError("");
    if (loadedMonthRef.current !== selectedMonth) setReport(null);
    try {
      const next = await ownerReportApi.data(shareId, selectedMonth);
      setReport(next); setInvalid(false); loadedMonthRef.current = selectedMonth;
    } catch (e) {
      if ([401, 404].includes(e?.response?.status)) {
        setReport(null); loadedMonthRef.current = null;
        setInvalid(e?.response?.status === 404);
      }
      setError(errMsg(e, "Laporan belum dapat dimuat."));
    } finally { busyRef.current = false; setBusy(false); }
  }, [shareId]);

  useEffect(() => { load(month); }, [load, month]);

  if (invalid) return <main className="min-h-screen bg-background p-8 text-center text-slate-200">Link laporan tidak tersedia.</main>;

  return <div className="min-h-screen bg-background text-foreground">
    <header className="border-b border-slate-800 bg-slate-950/90">
      <div className="mx-auto flex max-w-7xl items-center gap-2 px-4 py-4 sm:px-6">
        <BrandMark /><span className="font-bold">SAMPE · Laporan Owner</span>
      </div>
    </header>
    <main className="mx-auto max-w-7xl space-y-6 px-4 py-6 sm:px-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><h1 className="text-xl font-bold">Laporan KPI perusahaan</h1>
          <p className="text-xs text-slate-400">Data terbaru diambil saat halaman dibuka atau tombol diperbarui.</p></div>
        <div className="flex items-center gap-2">
          <select aria-label="Periode laporan" value={month} disabled={busy} onChange={(e) => setMonth(e.target.value)}
            className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm">
            {(report?.months || [month]).map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
          <button type="button" disabled={busy} aria-busy={busy} onClick={() => load(month)}
            className="inline-flex items-center gap-2 rounded-lg border border-slate-700 px-3 py-2 text-sm disabled:opacity-70">
            <RefreshCw aria-hidden="true" className={`h-4 w-4 ${busy ? "motion-safe:animate-spin" : ""}`} />
            {busy ? "Memperbarui…" : "Refresh Data"}
          </button>
        </div>
      </div>
      {busy && !report && <p className="text-sm text-slate-400">Memuat laporan…</p>}
      {busy && report && <p role="status" className="text-xs text-slate-400">Mengambil data terbaru…</p>}
      {error && <p role="alert" className="text-sm text-red-400">{error}</p>}
      {report && <>
        <p className="text-xs text-slate-500">Data diambil: {stamp(report.fetched_at)} · Entri/konfigurasi terakhir: {report.latest_created_at ? stamp(report.latest_created_at) : "belum ada"}</p>
        <Dashboard data={report.summary} compare={report.compare} readOnly />
        <section className="grid gap-3 sm:grid-cols-2">
          {["branding", "campaign"].map((key) => <div key={key} className="rounded-xl border border-slate-800 bg-[#161F30] p-4">
            <h2 className="font-semibold">{LABELS[key]}</h2>
            <p className="mt-2 text-xl font-bold">{rupiahFull(report.summary[key].achieved)}</p>
            <p className="text-xs text-slate-400">Target {rupiahFull(report.summary[key].monthly_target)} · Status {report.summary[key].status}</p>
          </div>)}
        </section>
        <section className="rounded-xl border border-slate-800 bg-[#161F30] p-4">
          <h2 className="mb-3 text-lg font-semibold">Data seluruh modul</h2>
          <div className="overflow-x-auto"><table className="w-full min-w-[560px] text-left text-sm">
            <thead><tr className="border-b border-slate-700 text-slate-400"><th className="p-2">Tanggal</th><th className="p-2">Modul</th><th className="p-2">Rincian</th></tr></thead>
            <tbody>{report.entries.map((entry, i) => <tr key={`${entry.date}-${entry.module}-${i}`} className="border-b border-slate-800 align-top">
              <td className="p-2">{entry.date}</td><td className="p-2">{LABELS[entry.module]}</td>
              <td className="p-2">{Object.entries(entry.data).map(([key, value]) => <div key={key}><span className="text-slate-400">{key}: </span>{String(value)}</div>)}</td>
            </tr>)}</tbody>
          </table></div>
        </section>
        <section className="rounded-xl border border-slate-800 bg-[#161F30] p-4">
          <h2 className="text-lg font-semibold">Ringkasan AI KPI</h2>
          {report.ai_analysis ? <>
            <p className="mt-2 text-xs text-slate-400">Dibuat {stamp(report.ai_analysis.generated_at)}{report.ai_analysis.stale ? " · KPI telah berubah; ringkasan perlu diperbarui oleh operator SAMPE" : ""}</p>
            <AiMarkdown text={report.ai_analysis.analysis} className="mt-3" />
          </> : <p className="mt-2 text-sm text-slate-400">Belum ada analisis untuk periode ini. Operator SAMPE dapat membuatnya dari dashboard.</p>}
        </section>
      </>}
    </main>
  </div>;
}
