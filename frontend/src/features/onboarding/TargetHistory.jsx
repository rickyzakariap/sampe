import { useEffect, useState } from "react";
import { Loader2, ArrowUpRight, ArrowDownRight } from "lucide-react";
import { api } from "@/lib/api";
import { rupiah } from "@/lib/format";
import { monthLabel } from "@/lib/export";

const ROWS = [
  ["target_sales", "Target Penjualan", "rp"], ["budget_ads", "Budget Ads", "rp"], ["budget_branding", "Budget Branding", "rp"],
  ["budget_campaign", "Budget Campaign", "rp"], ["budget_kol", "Budget KOL", "rp"], ["target_kol_count", "Jumlah KOL", "n"],
  ["live_team_count", "Tim Live", "n"], ["target_live_hours", "Durasi Live (jam)", "n"], ["target_live_revenue", "Omzet Live", "rp"],
];

const Change = ({ v }) => {
  if (v == null) return null;
  if (v === 0) return <span className="text-[10px] text-slate-500">0%</span>;
  const up = v > 0;
  const Icon = up ? ArrowUpRight : ArrowDownRight;
  return <span className={`inline-flex items-center text-[10px] font-semibold ${up ? "text-emerald-400" : "text-red-400"}`}><Icon className="h-3 w-3" />{up ? "+" : ""}{v}%</span>;
};

export const TargetHistory = ({ open }) => {
  const [rows, setRows] = useState(null);
  useEffect(() => { if (open) api.configHistory().then(setRows).catch(() => setRows([])); }, [open]);

  if (rows === null) return <Loader2 className="h-5 w-5 animate-spin text-emerald-400" />;
  if (!rows.length) return <p className="text-xs text-slate-500">Belum ada target tersimpan.</p>;
  return (
    <div data-testid="target-history-table" className="overflow-x-auto rounded-lg border border-slate-800">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-slate-800 bg-slate-900/60 text-slate-400">
            <th className="sticky left-0 bg-slate-900 px-3 py-2 text-left font-semibold">Target / Budget</th>
            {rows.map((r) => <th key={r.month} data-testid={`target-history-col-${r.month}`} className="px-3 py-2 text-right font-semibold whitespace-nowrap">{monthLabel(r.month)}</th>)}
          </tr>
        </thead>
        <tbody>
          {ROWS.map(([k, label, unit]) => (
            <tr key={k} className="border-b border-slate-800/60 last:border-0">
              <td className="sticky left-0 bg-slate-950 px-3 py-2 text-slate-300 whitespace-nowrap">{label}</td>
              {rows.map((r) => (
                <td key={r.month} data-testid={`target-history-${k}-${r.month}`} className="num px-3 py-2 text-right whitespace-nowrap">
                  <span className="text-slate-200">{unit === "rp" ? rupiah(r.values[k]) : r.values[k]}</span>
                  <span className="ml-1.5"><Change v={r.change_pct[k]} /></span>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
