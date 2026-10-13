import { useState, useEffect } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { api, currentMonth, errMsg } from "@/lib/api";
import { rupiahFull } from "@/lib/format";
import { Plus, Trash2, Wallet, Megaphone, Sparkles, Rocket, Radio, Users } from "lucide-react";

const PLATFORMS = ["TikTok", "Shopee", "Tokopedia", "WhatsApp", "Meta", "Lazada", "Website", "Offline"];
const BRAND_TYPES = ["Awareness", "Consideration", "Aktifasi Offline", "Buzzer/Clipper"];

const platformBadge = {
  TikTok: "text-pink-400 border-pink-500/30 bg-pink-500/10",
  Shopee: "text-orange-400 border-orange-500/30 bg-orange-500/10",
  Tokopedia: "text-emerald-400 border-emerald-500/30 bg-emerald-500/10",
  WhatsApp: "text-green-400 border-green-500/30 bg-green-500/10",
  Meta: "text-blue-400 border-blue-500/30 bg-blue-500/10",
  Lazada: "text-indigo-400 border-indigo-500/30 bg-indigo-500/10",
  Website: "text-purple-400 border-purple-500/30 bg-purple-500/10",
  Offline: "text-slate-300 border-slate-600 bg-slate-800",
};

const Field = ({ label, children }) => (
  <div className="space-y-1.5">
    <Label className="text-xs text-slate-400">{label}</Label>
    {children}
  </div>
);

const num = (c) => "num h-10 bg-slate-900/60 border-slate-700 " + (c || "");

const MODULES = [
  { key: "sales", label: "Penjualan", icon: Wallet },
  { key: "ads", label: "Ads", icon: Megaphone },
  { key: "branding", label: "Branding", icon: Sparkles },
  { key: "campaign", label: "Campaign", icon: Rocket },
  { key: "livestream", label: "Live Streaming", icon: Radio },
  { key: "kol", label: "KOL", icon: Users },
];

export const DailyInput = ({ month, onChanged, initialTab = "sales", missingToday = [], readOnly = false }) => {
  const [tab, setTab] = useState(initialTab);
  useEffect(() => setTab(initialTab), [initialTab]);
  const [entries, setEntries] = useState([]);
  const today = new Date().toISOString().slice(0, 10);

  const load = async (m) => setEntries(await api.getEntries(m, month));
  useEffect(() => { load(tab); }, [tab, month]);

  const add = async (data, date = today) => {
    try { await api.createEntry({ module: tab, date, data }); } catch (e) { return toast.error(errMsg(e)); }
    toast.success("Data tersimpan");
    await load(tab);
    onChanged?.();
  };
  const del = async (id) => {
    try { await api.deleteEntry(id); } catch (e) { return toast.error(errMsg(e)); }
    await load(tab);
    onChanged?.();
  };

  return (
    <div data-testid="daily-data-input-module" className="space-y-5">
      <div>
        <p className="text-xs font-semibold uppercase tracking-widest text-emerald-400">Modul Input Harian</p>
        <h1 className="text-3xl font-extrabold tracking-tight">List KPI</h1>
        <p className="text-sm text-slate-400">Catat data harian. Tambah banyak akun per platform (one-to-many).</p>
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="flex w-full flex-wrap h-auto gap-1 bg-slate-900/60 border border-slate-800 p-1">
          {MODULES.map((m) => (
            <TabsTrigger key={m.key} value={m.key} data-testid={`tab-${m.key}`} className="data-[state=active]:bg-emerald-500 data-[state=active]:text-slate-950 gap-1.5">
              <m.icon className="h-4 w-4" />{m.label}
              {missingToday.includes(m.key) && <span data-testid={`tab-missing-${m.key}`} title="Data hari ini belum diisi" className="h-1.5 w-1.5 rounded-full bg-amber-400" />}
            </TabsTrigger>
          ))}
        </TabsList>

        {MODULES.map((m) => (
          <TabsContent key={m.key} value={m.key} className="mt-5 space-y-4">
            {!readOnly && <FormFor module={m.key} onAdd={add} today={today} />}
            <EntryList module={m.key} entries={entries} onDelete={readOnly ? null : del} />
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
};

const emptyFor = (mod) => ({
  sales: { account: "", platform: "TikTok", omzet: "" },
  ads: { account: "", platform: "TikTok", spend: "", revenue: "", start_date: new Date().toISOString().slice(0, 10), end_date: new Date().toISOString().slice(0, 10) },
  branding: { type: "Awareness", spend: "", note: "" },
  campaign: { name: "", duration_days: "", budget: "" },
  livestream: { streamer: "", start_time: "19:00", end_time: "22:00", omzet: "" },
  kol: { name: "", budget: "", event: "", product: "" },
}[mod]);

const hoursBetween = (s, e) => {
  const [sh, sm] = s.split(":").map(Number);
  const [eh, em] = e.split(":").map(Number);
  let d = eh * 60 + em - (sh * 60 + sm);
  if (d < 0) d += 1440;
  return Math.round((d / 60) * 10) / 10;
};

const FormFor = ({ module, onAdd, today }) => {
  const [f, setF] = useState(emptyFor(module));
  const [date, setDate] = useState(today);
  useEffect(() => setF(emptyFor(module)), [module]);
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));

  const submit = async () => {
    const data = { ...f };
    if (module === "sales" && (!data.account || !data.omzet)) return toast.error("Isi nama akun & omzet");
    if (module === "ads") {
      if (!data.account || !data.spend) return toast.error("Isi akun & budget");
      if (!data.start_date || !data.end_date) return toast.error("Isi tanggal mulai & selesai iklan");
      if (data.end_date < data.start_date) return toast.error("Tanggal selesai tidak boleh sebelum tanggal mulai");
      data.spend = Number(data.spend); data.revenue = Number(data.revenue || 0);
      data.roi = data.spend ? Math.round((data.revenue / data.spend) * 100) / 100 : 0;
    }
    if (module === "campaign" && !data.name) return toast.error("Isi nama campaign");
    if (module === "livestream") {
      if (!data.streamer) return toast.error("Isi nama streamer");
      data.duration_hours = hoursBetween(data.start_time, data.end_time);
    }
    if (module === "kol" && !data.name) return toast.error("Isi nama KOL");
    ["omzet", "spend", "revenue", "budget", "duration_days"].forEach((k) => {
      if (k in data) data[k] = Number(data[k] || 0);
    });
    await onAdd(data, module === "ads" ? data.start_date : date);
    setF(emptyFor(module));
  };

  return (
    <Card className="bg-[#161F30] border-slate-800 p-5">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {module !== "ads" && (
          <Field label="Tanggal">
            <Input data-testid="input-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} className={num()} />
          </Field>
        )}

        {module === "sales" && (<>
          <Field label="Platform"><PlatformSelect value={f.platform} onChange={(v) => set("platform", v)} /></Field>
          <Field label="Nama Akun / Toko"><Input data-testid="input-account" value={f.account} onChange={(e) => set("account", e.target.value)} placeholder="TikTok Official" className={num()} /></Field>
          <Field label="Omzet (Rp)"><Input data-testid="input-omzet" type="number" value={f.omzet} onChange={(e) => set("omzet", e.target.value)} placeholder="5000000" className={num()} /></Field>
        </>)}

        {module === "ads" && (<>
          <Field label="Platform"><PlatformSelect value={f.platform} onChange={(v) => set("platform", v)} /></Field>
          <Field label="Nama Akun Ads"><Input data-testid="input-account" value={f.account} onChange={(e) => set("account", e.target.value)} placeholder="Meta Ads 1" className={num()} /></Field>
          <Field label="Budget Keluar (Rp)"><Input data-testid="input-spend" type="number" value={f.spend} onChange={(e) => set("spend", e.target.value)} placeholder="1500000" className={num()} /></Field>
          <Field label="Omzet dari Ads (Rp)"><Input data-testid="input-revenue" type="number" value={f.revenue} onChange={(e) => set("revenue", e.target.value)} placeholder="4500000" className={num()} /></Field>
          <Field label="Tanggal Mulai Iklan"><Input data-testid="input-ads-start" type="date" value={f.start_date} onChange={(e) => set("start_date", e.target.value)} className={num()} /></Field>
          <Field label="Tanggal Selesai Iklan"><Input data-testid="input-ads-end" type="date" value={f.end_date} min={f.start_date} onChange={(e) => set("end_date", e.target.value)} className={num()} /></Field>
        </>)}

        {module === "branding" && (<>
          <Field label="Jenis Branding">
            <Select value={f.type} onValueChange={(v) => set("type", v)}>
              <SelectTrigger data-testid="input-brand-type" className={num("w-full")}><SelectValue /></SelectTrigger>
              <SelectContent>{BRAND_TYPES.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent>
            </Select>
          </Field>
          <Field label="Budget Keluar (Rp)"><Input data-testid="input-spend" type="number" value={f.spend} onChange={(e) => set("spend", e.target.value)} placeholder="3000000" className={num()} /></Field>
          <Field label="Catatan"><Input data-testid="input-note" value={f.note} onChange={(e) => set("note", e.target.value)} placeholder="Event / detail" className={num()} /></Field>
        </>)}

        {module === "campaign" && (<>
          <Field label="Nama Campaign"><Input data-testid="input-name" value={f.name} onChange={(e) => set("name", e.target.value)} placeholder="Flash Sale 6.6" className={num()} /></Field>
          <Field label="Durasi (hari)"><Input data-testid="input-duration" type="number" value={f.duration_days} onChange={(e) => set("duration_days", e.target.value)} placeholder="3" className={num()} /></Field>
          <Field label="Budget (Rp)"><Input data-testid="input-budget" type="number" value={f.budget} onChange={(e) => set("budget", e.target.value)} placeholder="8000000" className={num()} /></Field>
        </>)}

        {module === "livestream" && (<>
          <Field label="Nama Streamer"><Input data-testid="input-streamer" value={f.streamer} onChange={(e) => set("streamer", e.target.value)} placeholder="Rani" className={num()} /></Field>
          <Field label="Jam Mulai"><Input data-testid="input-start" type="time" value={f.start_time} onChange={(e) => set("start_time", e.target.value)} className={num()} /></Field>
          <Field label="Jam Selesai"><Input data-testid="input-end" type="time" value={f.end_time} onChange={(e) => set("end_time", e.target.value)} className={num()} /></Field>
          <Field label="Omzet Live (Rp)"><Input data-testid="input-omzet" type="number" value={f.omzet} onChange={(e) => set("omzet", e.target.value)} placeholder="4000000" className={num()} /></Field>
        </>)}

        {module === "kol" && (<>
          <Field label="Nama KOL"><Input data-testid="input-name" value={f.name} onChange={(e) => set("name", e.target.value)} placeholder="KOL Micro 1" className={num()} /></Field>
          <Field label="Budget / Rate (Rp)"><Input data-testid="input-budget" type="number" value={f.budget} onChange={(e) => set("budget", e.target.value)} placeholder="3000000" className={num()} /></Field>
          <Field label="Event (opsional)"><Input data-testid="input-kol-event" value={f.event} onChange={(e) => set("event", e.target.value)} placeholder="Flash Sale 6.6" className={num()} /></Field>
          <Field label="Produk yang Ditampilkan (opsional)"><Input data-testid="input-kol-product" value={f.product} onChange={(e) => set("product", e.target.value)} placeholder="Kemeja Batik Slimfit" className={num()} /></Field>
        </>)}
      </div>
      <div className="mt-4 flex justify-end">
        <Button data-testid="daily-input-submit-button" onClick={submit} className="bg-emerald-500 hover:bg-emerald-600 text-slate-950 font-semibold">
          <Plus className="h-4 w-4 mr-1" /> Tambah Data
        </Button>
      </div>
    </Card>
  );
};

const PlatformSelect = ({ value, onChange }) => (
  <Select value={value} onValueChange={onChange}>
    <SelectTrigger data-testid="daily-input-platform-select" className={num("w-full")}><SelectValue /></SelectTrigger>
    <SelectContent>{PLATFORMS.map((p) => <SelectItem key={p} value={p}>{p}</SelectItem>)}</SelectContent>
  </Select>
);

const EntryList = ({ module, entries, onDelete }) => {
  if (!entries.length) return <p className="text-center text-sm text-slate-500 py-8">Belum ada data. Tambahkan entri pertamamu.</p>;
  return (
    <div data-testid={`${module}-entry-list`} className="rounded-xl border border-slate-800 bg-slate-900/40 overflow-hidden">
      {entries.map((e) => (
        <div key={e.id} data-testid="entry-row" className="flex items-center justify-between gap-3 border-b border-slate-800 px-4 py-3 last:border-0 hover:bg-slate-800/30">
          <div className="flex items-center gap-3 min-w-0">
            <span className="num text-xs text-slate-500 w-20 shrink-0">{e.date}</span>
            {e.data.platform && <Badge variant="outline" className={platformBadge[e.data.platform]}>{e.data.platform}</Badge>}
            <span className="truncate text-sm text-slate-200">{e.data.account || e.data.name || e.data.streamer || e.data.type}</span>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            <span className="num text-sm font-semibold text-emerald-400">{summary(module, e.data)}</span>
            {onDelete && <button data-testid="entry-delete" onClick={() => onDelete(e.id)} className="text-slate-500 hover:text-red-400 transition-colors"><Trash2 className="h-4 w-4" /></button>}
          </div>
        </div>
      ))}
    </div>
  );
};

const summary = (mod, d) => {
  if (mod === "sales") return rupiahFull(d.omzet);
  if (mod === "ads") return `${d.start_date ? `${d.start_date} s/d ${d.end_date} · ` : ""}${rupiahFull(d.spend)} · ROAS ${d.roi}x`;
  if (mod === "branding") return rupiahFull(d.spend);
  if (mod === "campaign") return `${rupiahFull(d.budget)} · ${d.duration_days}h`;
  if (mod === "livestream") return `${d.duration_hours}j · ${rupiahFull(d.omzet)}`;
  if (mod === "kol") return [d.event, d.product, rupiahFull(d.budget)].filter(Boolean).join(" · ");
  return "";
};
