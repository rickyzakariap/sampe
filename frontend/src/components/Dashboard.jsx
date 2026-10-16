import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  BarChart, Bar, Cell, LabelList,
} from "recharts";
import { LiveTeamTable, MonthCompare } from "@/components/DashboardExtras";
import { KpiAlertBanner } from "@/components/KpiAlertBanner";
import { rupiah, rupiahFull, pct, statusBg, statusLabel, statusColor } from "@/lib/format";
import { handleCardKeyDown } from "@/lib/cardInteraction.mjs";
import { TrendingUp, TrendingDown, Minus, Sparkles, Loader2, Clock, Target, Wallet, Radio, Users, Megaphone, ChevronRight } from "lucide-react";

const CHART = ["#10B981", "#3B82F6", "#F59E0B", "#a855f7", "#EF4444", "#22d3ee", "#ec4899", "#94a3b8"];

const TipBox = ({ active, payload, label }) =>
  active && payload?.length ? (
    <div className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-xs shadow-xl">
      <p className="mb-1 font-semibold text-slate-200">{label}</p>
      {payload.map((p, i) => (
        <p key={i} className="num" style={{ color: p.color }}>{p.name}: {rupiahFull(p.value)}</p>
      ))}
    </div>
  ) : null;

const metricCardInteraction = "group bg-[#161F30] border-slate-800 p-5 animate-fade-up motion-reduce:animate-none cursor-pointer transition-colors hover:border-emerald-500/40 active:border-emerald-500/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950";

const MetricCard = ({ testid, icon: Icon, label, m, unit = "rp", onClick }) => {
  const full = (v) => (unit === "rp" ? rupiahFull(v) : `${Number(v).toFixed(1)} jam`);
  return (
    <Card data-testid={testid} role="button" tabIndex={0} aria-label={`Lihat detail ${label}`} aria-haspopup="dialog" onClick={onClick} onKeyDown={(event) => handleCardKeyDown(event, onClick)} className={metricCardInteraction}>
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2 text-slate-400">
          <Icon className="h-4 w-4" />
          <span className="text-xs font-semibold uppercase tracking-wider">{label}</span>
        </div>
        <Badge variant="outline" className={statusBg[m.status]}>{statusLabel[m.status]}</Badge>
      </div>
      <p className="num mt-3 text-2xl sm:text-3xl font-bold text-white">{full(m.achieved)}</p>
      <p className="text-xs text-slate-400">dari target {full(m.monthly_target)}</p>
      <Progress value={Math.min(m.achieved_pct, 100)} className="mt-3 h-1.5 bg-slate-800" />
      <div className="mt-2 flex items-center justify-between text-xs">
        <span className="text-slate-400">Prorata s/d hari ini: <span className="num text-slate-200">{full(m.expected_to_date)}</span></span>
        <span className={`num font-semibold ${statusColor[m.status]}`}>{pct(m.achieved_pct)}</span>
      </div>
      <div className="mt-2 flex items-center justify-between text-xs">
        {m.gap > 0 ? (
          <span className="text-slate-400">Kurang <span className="num text-red-400">{full(m.gap)}</span> · butuh <span className="num text-amber-400">{full(m.needed_per_day)}/hari</span></span>
        ) : <span className="text-emerald-400">Target prorata tercapai</span>}
        <span className="inline-flex items-center gap-0.5 text-slate-400 group-hover:text-emerald-400 transition-colors">Detail <ChevronRight className="h-3 w-3" /></span>
      </div>
    </Card>
  );
};

const DetailDialog = ({ open, onClose, detail }) => {
  if (!detail) return null;
  const { title, subtitle, rows, unit, showRoi } = detail;
  const fmt = (v) => (unit === "jam" ? `${Number(v).toFixed(1)} jam` : rupiahFull(v));
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent data-testid="metric-detail-dialog" className="max-w-lg bg-slate-950 border-slate-800">
        <DialogHeader>
          <DialogTitle className="text-xl">{title}</DialogTitle>
          <DialogDescription className="sr-only">Rincian kontribusi {title}</DialogDescription>
          <p className="text-sm text-slate-400">{subtitle}</p>
        </DialogHeader>
        <div className="mt-2 space-y-3 max-h-[60vh] overflow-y-auto pr-1">
          {rows.length === 0 && <p className="text-sm text-slate-500 py-6 text-center">Belum ada data.</p>}
          {rows.map((r, i) => (
            <div key={i} data-testid="detail-row" className="rounded-lg border border-slate-800 bg-[#161F30] p-3">
              <div className="flex items-center justify-between gap-2">
                <span className="flex items-center gap-2 text-sm font-medium text-slate-200">
                  <span className="h-2.5 w-2.5 rounded-full shrink-0" style={{ background: CHART[i % CHART.length] }} />
                  {r.label}
                </span>
                <span className="num text-sm font-semibold text-emerald-400">{fmt(r.value)}{showRoi && r.roi != null ? ` · ${r.roi}x` : ""}</span>
              </div>
              <div className="mt-2 flex items-center gap-3">
                <div className="flex-1 h-1.5 rounded-full bg-slate-800 overflow-hidden">
                  <div className="h-full rounded-full" style={{ width: `${Math.min(r.pct_of_total, 100)}%`, background: CHART[i % CHART.length] }} />
                </div>
                <span className="num text-xs text-slate-400 w-28 text-right">{r.pct_of_total}% dari total</span>
              </div>
              <p className="num mt-1 text-xs text-slate-500">Kontribusi ke target KPI: <span className="text-slate-300">{r.pct_of_target}%</span></p>
              {r.period && <p data-testid="detail-row-period" className="num mt-1 text-xs text-slate-500">Periode iklan: <span className="text-slate-300">{r.period}</span></p>}
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
};

export const Dashboard = ({ data, compare, onAi, aiLoading = false, onGoInput, readOnly = false }) => {
  const [detail, setDetail] = useState(null);
  const [open, setOpen] = useState(false);
  if (!data) return null;
  const { sales, ads, kol, live_hours, live_revenue, trend, month_meta, sales_series, channel_breakdown, breakdowns } = data;
  const TrendIcon = trend.direction === "up" ? TrendingUp : trend.direction === "down" ? TrendingDown : Minus;
  const trendColor = trend.direction === "up" ? "text-emerald-400" : trend.direction === "down" ? "text-red-400" : "text-slate-400";
  const timeElapsedPct = (month_meta.days_elapsed / month_meta.days_in_month) * 100;
  const anyRed = [sales, ads, kol, live_hours, live_revenue].some((m) => m.status === "red");

  const show = (cfg) => { setDetail(cfg); setOpen(true); };
  const showAdsDetail = () => show({ title: "Efisiensi Ads per Platform", subtitle: "Belanja & ROAS per platform", rows: breakdowns.ads, unit: "rp", showRoi: true });

  return (
    <div className="space-y-6" data-testid="analytics-dashboard-view">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-emerald-400">Dashboard Harian</p>
          <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight">{data.config.company_name}</h1>
          <p className="text-sm text-slate-400">
            Periode {data.config.month} · Hari ke-<span className="num">{month_meta.days_elapsed}</span> dari <span className="num">{month_meta.days_in_month}</span>
          </p>
        </div>
        {!readOnly && <Button data-testid="ai-analysis-trigger-button" onClick={onAi} disabled={!onAi || aiLoading} aria-busy={aiLoading} className={`bg-amber-500 hover:bg-amber-600 text-slate-950 font-semibold ${anyRed ? "glow-danger" : ""}`}>
          {aiLoading ? <Loader2 className="h-4 w-4 mr-1.5 motion-safe:animate-spin" /> : <Sparkles className="h-4 w-4 mr-1.5 motion-safe:hover:animate-pulse" />}
          {aiLoading ? "Menganalisis…" : "Analisa AI"}
        </Button>}
      </div>

      <KpiAlertBanner data={data} onGoInput={readOnly ? undefined : onGoInput} />

      <Card data-testid="dashboard-time-vs-kpi-tracker" className="bg-[#161F30] border-slate-800 p-5">
        <div className="grid gap-5 sm:grid-cols-3">
          <div>
            <div className="flex items-center gap-2 text-slate-400"><Clock className="h-4 w-4" /><span className="text-xs font-semibold uppercase tracking-wider">Waktu Berjalan</span></div>
            <p className="num mt-2 text-2xl font-bold">{pct(timeElapsedPct)}</p>
            <Progress value={timeElapsedPct} className="mt-2 h-1.5 bg-slate-800" />
          </div>
          <div>
            <div className="flex items-center gap-2 text-slate-400"><Target className="h-4 w-4" /><span className="text-xs font-semibold uppercase tracking-wider">KPI Penjualan Tercapai</span></div>
            <p className={`num mt-2 text-2xl font-bold ${statusColor[sales.status]}`}>{pct(sales.achieved_pct)}</p>
            <Progress value={Math.min(sales.achieved_pct, 100)} className="mt-2 h-1.5 bg-slate-800" />
          </div>
          <div>
            <div className="flex items-center gap-2 text-slate-400"><TrendIcon className={`h-4 w-4 ${trendColor}`} /><span className="text-xs font-semibold uppercase tracking-wider">Trend Harian</span></div>
            <p className={`num mt-2 text-2xl font-bold ${trendColor}`}>{trend.pct > 0 ? "+" : ""}{pct(trend.pct)}</p>
            <p className="num text-xs text-slate-400 mt-1">{trend.abs >= 0 ? "+" : ""}{rupiahFull(trend.abs)} vs hari sebelumnya</p>
          </div>
        </div>
      </Card>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" data-testid="dashboard-prorate-metric-card">
        <MetricCard testid="metric-sales" icon={Wallet} label="Penjualan" m={sales}
          onClick={() => show({ title: "Detail Penjualan", subtitle: "Kontribusi omzet per platform", rows: breakdowns.sales, unit: "rp" })} />
        <MetricCard testid="metric-ads" icon={Megaphone} label="Ads Spend" m={ads}
          onClick={() => show({ title: "Detail Belanja Ads", subtitle: "Budget & ROAS per platform", rows: breakdowns.ads, unit: "rp", showRoi: true })} />
        <MetricCard testid="metric-live-revenue" icon={Radio} label="Omzet Live" m={live_revenue}
          onClick={() => show({ title: "Detail Omzet Live", subtitle: "Kontribusi omzet per streamer", rows: breakdowns.live_revenue, unit: "rp" })} />
        <MetricCard testid="metric-live-hours" icon={Clock} label="Durasi Live" m={live_hours} unit="jam"
          onClick={() => show({ title: "Detail Durasi Live", subtitle: "Jam live per streamer", rows: breakdowns.live_hours, unit: "jam" })} />
        <MetricCard testid="metric-kol" icon={Users} label="Budget KOL" m={kol}
          onClick={() => show({ title: "Detail Budget KOL", subtitle: "Budget per KOL", rows: breakdowns.kol, unit: "rp" })} />
        <Card data-testid="metric-ads-roi" role="button" tabIndex={0} aria-label="Lihat detail Efisiensi Ads per Platform" aria-haspopup="dialog" onClick={showAdsDetail} onKeyDown={(event) => handleCardKeyDown(event, showAdsDetail)} className={metricCardInteraction}>
          <div className="flex items-center gap-2 text-slate-400"><TrendingUp className="h-4 w-4" /><span className="text-xs font-semibold uppercase tracking-wider">Efisiensi Ads</span></div>
          <p className="num mt-3 text-2xl sm:text-3xl font-bold text-white">{ads.roi.toFixed(2)}x</p>
          <p className="text-xs text-slate-400">ROAS · Revenue {rupiah(ads.revenue)}</p>
          <div className="mt-3 flex items-center justify-between text-xs">
            <span className="text-slate-400">CPA rata-rata</span>
            <span className="num text-slate-200">{rupiahFull(ads.cpa)}</span>
          </div>
          <div className="mt-1 flex items-center justify-between text-xs">
            <span className="text-slate-400">KOL terealisasi</span>
            <span className="num text-slate-200">{kol.realized_count}/{kol.target_count}</span>
          </div>
          <div className="mt-2 flex justify-end text-xs"><span className="inline-flex items-center gap-0.5 text-slate-400 group-hover:text-emerald-400 transition-colors">Detail <ChevronRight className="h-3 w-3" /></span></div>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-5">
        <Card data-testid="dashboard-sales-chart" className="bg-[#161F30] border-slate-800 p-5 lg:col-span-3">
          <h3 className="text-lg font-semibold">Tren Penjualan Harian</h3>
          <p className="text-xs text-slate-500 mb-3">Akumulasi omzet seluruh channel per hari</p>
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={sales_series} margin={{ left: -12, right: 8, top: 8 }}>
              <defs>
                <linearGradient id="g1" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#10B981" stopOpacity={0.5} />
                  <stop offset="100%" stopColor="#10B981" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1F2937" vertical={false} />
              <XAxis dataKey="date" tickFormatter={(d) => d.slice(-2)} stroke="#64748b" fontSize={11} />
              <YAxis tickFormatter={(v) => rupiah(v)} stroke="#64748b" fontSize={11} />
              <Tooltip content={<TipBox />} />
              <Area type="monotone" dataKey="omzet" name="Omzet" stroke="#10B981" strokeWidth={2} fill="url(#g1)" />
            </AreaChart>
          </ResponsiveContainer>
        </Card>

        <Card data-testid="dashboard-channel-chart" className="bg-[#161F30] border-slate-800 p-5 lg:col-span-2">
          <h3 className="text-lg font-semibold">Penjualan per Channel</h3>
          <p className="text-xs text-slate-500 mb-3">Angka = % kontribusi tiap platform ke target KPI penjualan</p>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={channel_breakdown} layout="vertical" margin={{ left: 8, right: 56 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1F2937" horizontal={false} />
              <XAxis type="number" tickFormatter={(v) => rupiah(v)} stroke="#64748b" fontSize={11} />
              <YAxis type="category" dataKey="platform" stroke="#94a3b8" fontSize={11} width={70} />
              <Tooltip content={<TipBox />} cursor={{ fill: "#1e293b55" }} />
              <Bar dataKey="omzet" name="Omzet" radius={[0, 6, 6, 0]}>
                {channel_breakdown.map((_, i) => <Cell key={i} fill={CHART[i % CHART.length]} />)}
                <LabelList dataKey="pct_of_target" position="right" formatter={(v) => `${v}% target`} fill="#cbd5e1" fontSize={10} className="num" />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-5">
        <LiveTeamTable rows={data.live_team || []} />
        <MonthCompare rows={compare || []} />
      </div>

      <DetailDialog open={open} onClose={() => setOpen(false)} detail={detail} />
    </div>
  );
};
