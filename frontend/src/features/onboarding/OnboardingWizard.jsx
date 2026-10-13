import { useState } from "react";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { rupiahFull } from "@/lib/format";
import { SCALES, STEP_FIELDS, guessScale } from "./presets";
import { ScalePicker, ExampleButton } from "./ExamplePicker";
import { currentMonth } from "@/lib/api";
import { Building2, Target, Megaphone, Sparkles, Rocket, Users, Radio, Check, ArrowRight, ArrowLeft, Lightbulb, Copy } from "lucide-react";

const STEPS = [
  { icon: Building2, title: "Profil Perusahaan", desc: "Nama toko / project UMKM kamu",
    tip: () => "Pakai nama toko yang sama seperti di marketplace agar laporan mudah dikenali. Periode = bulan yang mau kamu pantau." },
  { icon: Target, title: "Target Penjualan", desc: "Total omzet target bulan ini",
    tip: (f) => `Jumlahkan target omzet semua channel (TikTok, Shopee, offline, dll) selama 1 bulan. Patokan aman: rata-rata omzet 3 bulan terakhir + 10–20%.${n(f.target_sales) ? ` Artinya kamu perlu ±${rupiahFull(perDay(f.target_sales, f.month))} per hari.` : ""}` },
  { icon: Megaphone, title: "Budget Ads", desc: "Anggaran iklan bulanan",
    tip: (f) => `Total uang iklan berbayar sebulan (Shopee Ads, TikTok Ads, Meta Ads). Umumnya 5–15% dari target penjualan.${ratio(f.budget_ads, f.target_sales)}` },
  { icon: Sparkles, title: "Budget Branding", desc: "Awareness, consideration, aktivasi",
    tip: () => "Biaya membangun nama toko, bukan iklan jualan langsung: konten awareness, buzzer/clipper, event offline. Isi 0 jika belum ada." },
  { icon: Rocket, title: "Budget Campaign", desc: "Promo, voucher, tanggal kembar",
    tip: (f) => `Perkiraan subsidi promo yang kamu tanggung: voucher, gratis ongkir, flash sale tanggal kembar (6.6, 7.7).${ratio(f.budget_campaign, f.target_sales)}` },
  { icon: Users, title: "KOL Activation", desc: "Budget & target jumlah KOL",
    tip: (f) => `Total fee affiliator/influencer sebulan & jumlah orangnya. Contoh: 10 KOL × Rp3 juta = Rp30 juta.${n(f.budget_kol) && n(f.target_kol_count) ? ` Rata-rata kamu: ${rupiahFull(n(f.budget_kol) / n(f.target_kol_count))} per KOL.` : ""}` },
  { icon: Radio, title: "Live Streaming", desc: "Tim, durasi & omzet live",
    tip: (f) => `Durasi = total jam live semua host sebulan (mis. 2 sesi × 3 jam × 30 hari = 180 jam).${n(f.target_live_revenue) && n(f.target_live_hours) ? ` Target omzetmu setara ${rupiahFull(n(f.target_live_revenue) / n(f.target_live_hours))} per jam live.` : ""}` },
];

function n(v) { return Number(v) || 0; }
function perDay(v, month) { return n(v) / new Date(Number(month.slice(0, 4)), Number(month.slice(5, 7)), 0).getDate(); }
function ratio(v, base) { return n(v) && n(base) ? ` Isianmu = ${((n(v) / n(base)) * 100).toFixed(1)}% dari target penjualan.` : ""; }

const Tip = ({ text }) => (
  <div data-testid="wizard-tip" className="flex gap-2.5 rounded-lg border border-sky-500/25 bg-sky-500/5 p-3 text-xs leading-relaxed text-slate-300">
    <Lightbulb className="h-4 w-4 shrink-0 text-sky-400" />
    <p>{text}</p>
  </div>
);

const empty = {
  company_name: "", month: currentMonth(), target_sales: "", budget_ads: "", budget_branding: "",
  budget_campaign: "", budget_kol: "", target_kol_count: "", live_team_count: "",
  target_live_hours: "", target_live_revenue: "",
};

const Money = ({ id, value, onChange, placeholder }) => (
  <div>
    <Input
      data-testid={id}
      type="number"
      min="0"
      inputMode="numeric"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className="num h-12 text-lg bg-slate-900/60 border-slate-700"
    />
    {value !== "" && Number(value) > 0 && (
      <p className="mt-1 text-xs text-emerald-400 num">{rupiahFull(value)}</p>
    )}
  </div>
);

export const OnboardingWizard = ({ open, onComplete, onSeed, initial, onCancel }) => {
  const [step, setStep] = useState(0);
  const [form, setForm] = useState(initial || empty);
  const copyMode = Boolean(initial);
  const [scale, setScale] = useState(null);
  const activeScale = scale || guessScale(form.target_sales);
  const fill = (s, fields) => setForm((f) => ({ ...f, ...Object.fromEntries(fields.map((k) => [k, String(SCALES[s].values[k])])) }));
  const pickScale = (s) => { setScale(s); fill(s, STEP_FIELDS[1]); };
  const useExample = () => fill(activeScale, STEP_FIELDS[step]);
  const set = (k) => (v) => setForm((f) => ({ ...f, [k]: v }));
  const Icon = STEPS[step].icon;
  const last = step === STEPS.length - 1;

  const canNext = () => {
    if (step === 0) return form.company_name.trim().length > 1;
    return true;
  };

  const submit = async () => {
    const payload = Object.fromEntries(
      Object.entries(form).map(([k, v]) =>
        ["company_name", "month"].includes(k) ? [k, v] : [k, Number(v) || 0]
      )
    );
    await onComplete(payload);
  };

  return (
    <Dialog open={open}>
      <DialogContent
        data-testid="kpi-onboarding-wizard"
        className="max-w-xl bg-slate-950 border-slate-800 p-0 gap-0 overflow-hidden"
        hideClose
      >
        <DialogTitle className="sr-only">Setup KPI</DialogTitle>
        <DialogDescription className="sr-only">Wizard pengaturan target KPI bulanan</DialogDescription>
        <div className="flex items-center gap-1.5 px-6 pt-6">
          {STEPS.map((_, i) => (
            <div key={i} className={`h-1.5 flex-1 rounded-full transition-colors duration-300 ${i <= step ? "bg-emerald-500" : "bg-slate-800"}`} />
          ))}
        </div>

        <div className="px-6 pt-6 pb-2">
          <p className="text-xs font-semibold uppercase tracking-widest text-emerald-400">
            {copyMode ? "Salin Target" : "Setup KPI"} · Langkah {step + 1}/{STEPS.length}
          </p>
          {copyMode && step === 0 && (
            <p data-testid="wizard-copy-note" className="mt-2 flex items-center gap-1.5 text-xs text-slate-400">
              <Copy className="h-3.5 w-3.5 text-emerald-400" /> Angka disalin dari bulan sebelumnya. Cek & ubah bila perlu, lalu simpan.
            </p>
          )}
          <div className="mt-3 flex items-center gap-3">
            <div className="grid place-items-center h-12 w-12 rounded-xl bg-emerald-500/10 border border-emerald-500/30">
              <Icon className="h-6 w-6 text-emerald-400" />
            </div>
            <div>
              <h2 className="text-2xl font-extrabold tracking-tight">{STEPS[step].title}</h2>
              <p className="text-sm text-slate-400">{STEPS[step].desc}</p>
            </div>
          </div>
        </div>

        <div className="px-6 py-5 min-h-[180px] space-y-4" key={step}>
          <div className="animate-fade-up space-y-4">
            {step === 0 && (
              <div data-testid="onboarding-wizard-step-1-company" className="space-y-2">
                <Label>Nama Toko / Perusahaan</Label>
                <p className="text-xs text-slate-500">Nama ini dipakai di dashboard, laporan, dan data demo.</p>
                <Input data-testid="wizard-company-name" value={form.company_name} onChange={(e) => set("company_name")(e.target.value)} placeholder="Ketik nama toko kamu" autoFocus className="h-12 bg-slate-900/60 border-slate-700" />
                <Label className="pt-2 block">Periode (Bulan)</Label>
                <Input data-testid="wizard-month" type="month" value={form.month} onChange={(e) => set("month")(e.target.value)} className="h-12 bg-slate-900/60 border-slate-700" />
              </div>
            )}
            {step === 1 && (
              <div data-testid="onboarding-wizard-step-2-sales" className="space-y-2">
                <ScalePicker scale={scale} onPick={pickScale} />
                <Label className="pt-2 block">Target Penjualan per Bulan (Rp)</Label>
                <Money id="wizard-target-sales" value={form.target_sales} onChange={set("target_sales")} placeholder="500000000" />
              </div>
            )}
            {step === 2 && (
              <div data-testid="onboarding-wizard-step-3-ads" className="space-y-2">
                <Label>Budget Ads Bulanan (Rp)</Label>
                <Money id="wizard-budget-ads" value={form.budget_ads} onChange={set("budget_ads")} placeholder="60000000" />
              </div>
            )}
            {step === 3 && (
              <div data-testid="onboarding-wizard-step-4-branding" className="space-y-2">
                <Label>Budget Branding Bulanan (Rp)</Label>
                <Money id="wizard-budget-branding" value={form.budget_branding} onChange={set("budget_branding")} placeholder="25000000" />
              </div>
            )}
            {step === 4 && (
              <div data-testid="onboarding-wizard-step-5-campaign" className="space-y-2">
                <Label>Budget Campaign Bulanan (Rp)</Label>
                <Money id="wizard-budget-campaign" value={form.budget_campaign} onChange={set("budget_campaign")} placeholder="30000000" />
              </div>
            )}
            {step === 5 && (
              <div data-testid="onboarding-wizard-step-6-kol" className="grid grid-cols-2 gap-4">
                <div className="space-y-2 col-span-2 sm:col-span-1">
                  <Label>Budget KOL (Rp)</Label>
                  <Money id="wizard-budget-kol" value={form.budget_kol} onChange={set("budget_kol")} placeholder="40000000" />
                </div>
                <div className="space-y-2 col-span-2 sm:col-span-1">
                  <Label>Target Jumlah KOL</Label>
                  <Input data-testid="wizard-target-kol-count" type="number" min="0" value={form.target_kol_count} onChange={(e) => set("target_kol_count")(e.target.value)} placeholder="12" className="num h-12 bg-slate-900/60 border-slate-700" />
                </div>
              </div>
            )}
            {step === 6 && (
              <div data-testid="onboarding-wizard-step-7-livestream" className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Total Anggota Tim Live</Label>
                  <Input data-testid="wizard-live-team" type="number" min="0" value={form.live_team_count} onChange={(e) => set("live_team_count")(e.target.value)} placeholder="4" className="num h-12 bg-slate-900/60 border-slate-700" />
                </div>
                <div className="space-y-2">
                  <Label>Target Durasi Live (jam/bln)</Label>
                  <Input data-testid="wizard-live-hours" type="number" min="0" value={form.target_live_hours} onChange={(e) => set("target_live_hours")(e.target.value)} placeholder="180" className="num h-12 bg-slate-900/60 border-slate-700" />
                </div>
                <div className="space-y-2 col-span-2">
                  <Label>Target Omzet Live Bulanan (Rp)</Label>
                  <Money id="wizard-live-revenue" value={form.target_live_revenue} onChange={set("target_live_revenue")} placeholder="150000000" />
                </div>
              </div>
            )}
            {step >= 2 && <ExampleButton scale={activeScale} onUse={useExample} />}
            <Tip text={STEPS[step].tip(form)} />
          </div>
        </div>

        <div className="flex items-center justify-between gap-3 border-t border-slate-800 bg-slate-900/40 px-6 py-4">
          {step === 0 && copyMode ? (
            <Button data-testid="wizard-cancel" variant="ghost" className="text-slate-400" onClick={onCancel}>Batal</Button>
          ) : step === 0 ? (
            <Button data-testid="wizard-seed-demo" variant="ghost" disabled={!canNext()} title={canNext() ? "" : "Isi nama toko dulu"}
              className="text-slate-400 hover:text-emerald-400" onClick={() => onSeed(form.company_name.trim())}>
              Coba dengan Data Demo
            </Button>
          ) : (
            <Button variant="outline" className="border-slate-700" onClick={() => setStep((s) => s - 1)} data-testid="wizard-back">
              <ArrowLeft className="h-4 w-4 mr-1" /> Kembali
            </Button>
          )}
          {last ? (
            <Button data-testid="wizard-finish" onClick={submit} className="bg-emerald-500 hover:bg-emerald-600 text-slate-950 font-semibold">
              <Check className="h-4 w-4 mr-1" /> {copyMode ? "Simpan Target Bulan Ini" : "Selesai & Buat Dashboard"}
            </Button>
          ) : (
            <Button data-testid="wizard-next" disabled={!canNext()} onClick={() => setStep((s) => s + 1)} className="bg-emerald-500 hover:bg-emerald-600 text-slate-950 font-semibold">
              Lanjut <ArrowRight className="h-4 w-4 ml-1" />
            </Button>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};
