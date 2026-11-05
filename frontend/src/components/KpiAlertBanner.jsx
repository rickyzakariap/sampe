import { AlertTriangle, ClipboardList, ArrowRight } from "lucide-react";
import { pct } from "@/lib/format";

export const MODULE_LABEL = { sales: "Penjualan", ads: "Ads", livestream: "Live Streaming" };

const KPIS = [
  ["sales", "Penjualan"], ["ads", "Ads Spend"], ["live_revenue", "Omzet Live"], ["live_hours", "Durasi Live"], ["kol", "Budget KOL"],
];

export const KpiAlertBanner = ({ data, onGoInput }) => {
  const missing = data.missing_today || [];
  const behind = KPIS.filter(([k]) => data[k]?.status === "red" || data[k]?.status === "amber");
  if (!missing.length && !behind.length) return null;
  return (
    <div data-testid="kpi-alert-banner" className="grid gap-3 md:grid-cols-2">
      {behind.length > 0 && (
        <div data-testid="kpi-alert-behind" className="rounded-xl border border-red-500/30 bg-red-500/5 p-4">
          <p className="flex items-center gap-2 text-sm font-semibold text-red-300"><AlertTriangle className="h-4 w-4" /> {behind.length} KPI di bawah target harian</p>
          <ul className="mt-2 space-y-1">
            {behind.map(([k, label]) => (
              <li key={k} className="num text-xs text-slate-300">
                <span className={data[k].status === "red" ? "text-red-400" : "text-amber-400"}>●</span> {label}: {pct(data[k].pace_pct)} dari target prorata hari ini
              </li>
            ))}
          </ul>
          {missing.length > 0 && <p className="mt-2 text-[11px] text-slate-500">Catatan: sebagian bisa karena data hari ini belum diisi.</p>}
        </div>
      )}
      {missing.length > 0 && (
        <div data-testid="kpi-alert-missing" className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-4">
          <p className="flex items-center gap-2 text-sm font-semibold text-amber-300"><ClipboardList className="h-4 w-4" /> Data hari ini belum diisi</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {missing.map((m) => (
              onGoInput ? <button key={m} data-testid={`kpi-alert-missing-${m}`} onClick={() => onGoInput(m)}
                className="inline-flex items-center gap-1 rounded-full border border-amber-500/30 bg-slate-900/60 px-3 py-1 text-xs text-amber-200 transition-colors hover:bg-amber-500/15">
                {MODULE_LABEL[m]} <ArrowRight className="h-3 w-3" />
              </button> : <span key={m} className="rounded-full border border-amber-500/30 bg-slate-900/60 px-3 py-1 text-xs text-amber-200">{MODULE_LABEL[m]}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
