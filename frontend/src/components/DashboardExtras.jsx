import { Card } from "@/components/ui/card";
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
} from "recharts";
import { rupiah, rupiahFull } from "@/lib/format";
import { monthLabel } from "@/lib/export";
import { Radio, CalendarRange, TrendingUp, TrendingDown } from "lucide-react";

const SERIES = [
  { key: "sales", name: "Omzet", color: "#10B981" },
  { key: "ads_spend", name: "Belanja Ads", color: "#F59E0B" },
  { key: "live_omzet", name: "Omzet Live", color: "#3B82F6" },
];

export const LiveTeamTable = ({ rows }) => {
  const best = rows[0]?.streamer;
  return (
    <Card data-testid="live-team-table" className="bg-[#161F30] border-slate-800 p-5 lg:col-span-2">
      <div className="flex items-center gap-2"><Radio className="h-4 w-4 text-pink-400" /><h3 className="text-lg font-semibold">Log Tim Live</h3></div>
      <p className="text-xs text-slate-500 mb-3">Performa tiap host bulan ini, diurutkan dari omzet tertinggi</p>
      {rows.length === 0 ? <p className="py-10 text-center text-sm text-slate-500">Belum ada data live streaming.</p> : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-800 text-left text-xs uppercase tracking-wider text-slate-500">
                <th className="py-2 pr-2 font-semibold">Host</th>
                <th className="py-2 px-2 font-semibold text-right">Sesi</th>
                <th className="py-2 px-2 font-semibold text-right">Jam</th>
                <th className="py-2 px-2 font-semibold text-right">Omzet</th>
                <th className="py-2 pl-2 font-semibold text-right">Rp/Jam</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.streamer} data-testid={`live-team-row-${r.streamer}`} className="border-b border-slate-800/60 last:border-0 hover:bg-slate-800/30">
                  <td className="py-2.5 pr-2">
                    <span className="font-medium text-slate-200">{r.streamer}</span>
                    {r.streamer === best && rows.length > 1 && <span className="ml-1.5 rounded bg-emerald-500/15 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-400">TOP</span>}
                    <p className="num text-[11px] text-slate-500">{r.pct_of_total}% omzet live · {r.pct_of_target}% target</p>
                  </td>
                  <td className="num py-2.5 px-2 text-right text-slate-300">{r.sessions}</td>
                  <td className="num py-2.5 px-2 text-right text-slate-300">{r.hours}</td>
                  <td className="num py-2.5 px-2 text-right font-semibold text-emerald-400">{rupiah(r.omzet)}</td>
                  <td className="num py-2.5 pl-2 text-right text-slate-400">{rupiah(r.omzet_per_hour)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
};

const CompareTip = ({ active, payload, label }) =>
  active && payload?.length ? (
    <div className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-xs shadow-xl">
      <p className="mb-1 font-semibold text-slate-200">{label}</p>
      {payload.map((p) => <p key={p.dataKey} className="num" style={{ color: p.color }}>{p.name}: {rupiahFull(p.value)}</p>)}
      <p className="num mt-1 text-slate-400">Target tercapai: {payload[0].payload.achieved_pct}%</p>
    </div>
  ) : null;

export const MonthCompare = ({ rows }) => {
  const data = rows.map((r) => ({ ...r, label: monthLabel(r.month) }));
  const [prev, cur] = [data[data.length - 2], data[data.length - 1]];
  const delta = prev?.sales ? ((cur.sales - prev.sales) / prev.sales) * 100 : null;
  const Up = delta >= 0 ? TrendingUp : TrendingDown;
  return (
    <Card data-testid="month-compare-chart" className="bg-[#161F30] border-slate-800 p-5 lg:col-span-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2"><CalendarRange className="h-4 w-4 text-emerald-400" /><h3 className="text-lg font-semibold">Perbandingan 3 Bulan</h3></div>
          <p className="text-xs text-slate-500">Omzet, belanja ads & omzet live per bulan</p>
        </div>
        {delta != null && (
          <span data-testid="month-compare-delta" className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-semibold num ${delta >= 0 ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400" : "border-red-500/30 bg-red-500/10 text-red-400"}`}>
            <Up className="h-3 w-3" />{delta >= 0 ? "+" : ""}{delta.toFixed(1)}% omzet vs bulan lalu
          </span>
        )}
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2">
        {data.map((r) => (
          <div key={r.month} data-testid={`month-compare-pct-${r.month}`} className="rounded-lg border border-slate-800 bg-slate-900/50 px-3 py-2">
            <p className="text-[11px] text-slate-500">{r.label}</p>
            <p className={`num text-lg font-bold ${r.achieved_pct >= 100 ? "text-emerald-400" : r.achieved_pct >= 80 ? "text-amber-400" : "text-slate-200"}`}>{r.achieved_pct}%</p>
            <p className="text-[10px] text-slate-500">pencapaian target</p>
          </div>
        ))}
      </div>
      <ResponsiveContainer width="100%" height={230}>
        <BarChart data={data} margin={{ left: -8, right: 8, top: 12 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1F2937" vertical={false} />
          <XAxis dataKey="label" stroke="#64748b" fontSize={11} />
          <YAxis tickFormatter={(v) => rupiah(v)} stroke="#64748b" fontSize={11} />
          <Tooltip content={<CompareTip />} cursor={{ fill: "#1e293b55" }} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          {SERIES.map((s) => <Bar key={s.key} dataKey={s.key} name={s.name} fill={s.color} radius={[4, 4, 0, 0]} />)}
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );
};
