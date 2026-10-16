import { useEffect, useState, useCallback, useRef } from "react";
import "@/App.css";
import { Toaster } from "@/components/ui/sonner";
import { TopNavbar } from "@/components/TopNavbar";
import { Dashboard } from "@/components/Dashboard";
import { DailyInput } from "@/components/DailyInput";
import { AiAnalysisPanel } from "@/components/AiAnalysisPanel";
import { OnboardingWizard, SettingsDialog, CopyTargetReminder, useOnboarding } from "@/features/onboarding";
import { ReadOnlyBanner, RenewSoonBanner } from "@/features/auth/LicenseMenu";
import { api, currentMonth, shiftMonth } from "@/lib/api";
import { exportCSV, exportPDF, monthLabel } from "@/lib/export";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import { OwnerReportShare } from "@/features/owner-report/OwnerReportShare";
import { Skeleton } from "@/components/ui/skeleton";

function DashboardSkeleton() {
  return <div role="status" aria-label="Memuat dashboard KPI" className="space-y-5 motion-reduce:animate-none">
    <span className="sr-only">Memuat dashboard KPI…</span>
    <Skeleton className="h-8 w-48 motion-reduce:animate-none" />
    <div className="grid gap-4 sm:grid-cols-3">
      {[0, 1, 2].map((i) => <Skeleton key={i} className="h-28 motion-reduce:animate-none" />)}
    </div>
    <Skeleton className="h-48 motion-reduce:animate-none" />
  </div>;
}

function App({ license, writable, logout, renewUrl, user }) {
  const readOnly = !writable;
  const [booting, setBooting] = useState(true);
  const [month, setMonth] = useState(currentMonth());
  const [view, setView] = useState("dashboard");
  const [inputTab, setInputTab] = useState("sales");
  const [dash, setDash] = useState(null);
  const [dashLoading, setDashLoading] = useState(false);
  const [compare, setCompare] = useState([]);
  const [months, setMonths] = useState([]);
  const [settingsOpen, setSettingsOpen] = useState(false);

  const [aiOpen, setAiOpen] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiResult, setAiResult] = useState(null);
  const [aiError, setAiError] = useState(null);
  const aiPendingRef = useRef(false);

  const loadDash = useCallback(async (m) => {
    setDashLoading(true);
    try {
      try { setDash(await api.dashboard(m)); } catch { setDash(null); }
      try { setCompare(await api.compare(m)); } catch { setCompare([]); }
    } finally { setDashLoading(false); }
  }, []);

  const onReady = useCallback(async (m) => {
    setMonth(m);
    try { setMonths(await api.months()); } catch { /* noop */ }
    await loadDash(m);
  }, [loadDash]);

  const onCleared = useCallback(() => {
    setDash(null); setCompare([]); setMonths([]); setMonth(currentMonth()); setView("dashboard");
  }, []);

  const ob = useOnboarding({ onReady, onCleared, readOnly });
  const { boot } = ob;

  useEffect(() => { boot().finally(() => setBooting(false)); }, [boot]);

  const changeMonth = async (m) => { setMonth(m); setDash(null); await loadDash(m); };

  const goInput = (tab = "sales") => { setInputTab(tab); setView("input"); };

  const doExport = async (kind) => {
    if (!dash) return toast.error("Belum ada data untuk diekspor");
    try {
      const entries = await api.getEntries(undefined, month);
      if (kind === "csv") exportCSV(dash, entries);
      else await exportPDF(dash, entries);
      toast.success(`Laporan ${kind.toUpperCase()} diunduh`);
    } catch {
      toast.error("Gagal mengekspor laporan");
    }
  };

  const runAi = async () => {
    if (aiPendingRef.current || readOnly) return;
    aiPendingRef.current = true;
    setAiOpen(true); setAiLoading(true); setAiError(null); setAiResult(null);
    try {
      setAiResult(await api.analyze(month));
    } catch (e) {
      setAiError(e?.response?.data?.detail || "Gagal menjalankan analisa AI.");
    } finally {
      aiPendingRef.current = false;
      setAiLoading(false);
    }
  };

  if (booting) {
    return (
      <div className="min-h-screen grid place-items-center bg-background text-slate-400">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-emerald-400" />
          <p className="text-sm">Memuat SAMPE…</p>
        </div>
      </div>
    );
  }

  const overall = dash
    ? (() => {
        const st = [dash.sales, dash.ads, dash.kol, dash.live_revenue].map((m) => m.status);
        return st.includes("red") ? "red" : st.includes("amber") ? "amber" : "green";
      })()
    : null;

  return (
    <div className="min-h-screen bg-background text-foreground">
      {readOnly && <ReadOnlyBanner renewUrl={renewUrl} />}
      <RenewSoonBanner license={license} renewUrl={renewUrl} />
      <TopNavbar
        license={license}
        user={user}
        readOnly={readOnly}
        onLogout={logout}
        view={view}
        setView={setView}
        company={ob.config?.company_name}
        overallStatus={overall}
        onQuickAdd={() => goInput(inputTab)}
        onAi={runAi}
        aiLoading={aiLoading}
        months={months}
        month={month}
        onMonthChange={changeMonth}
        onExportCsv={() => doExport("csv")}
        onExportPdf={() => doExport("pdf")}
        onEditCompany={() => setSettingsOpen(true)}
      />
      <SettingsDialog open={settingsOpen} onClose={() => setSettingsOpen(false)} current={ob.config?.company_name}
        onSave={ob.saveCompany} onReset={ob.resetAll} onCopyNext={() => ob.startCopy()} readOnly={readOnly}
        nextMonthLabel={ob.config ? monthLabel(shiftMonth(ob.config.month, 1)) : ""} />

      <main className="mx-auto max-w-7xl px-4 sm:px-6 py-6 sm:py-8">
        {view === "dashboard" && writable && <OwnerReportShare />}
        {view === "dashboard" && (
          dashLoading ? <DashboardSkeleton /> : dash ? (
            <div className="space-y-6">
              {dash.has_config === false && !readOnly && (
                <CopyTargetReminder month={month} fromMonth={dash.config.month} onCopy={ob.startCopy} />
              )}
              <Dashboard data={dash} compare={compare} onAi={readOnly ? undefined : runAi} aiLoading={aiLoading} onGoInput={goInput} />
            </div>
          ) : (
            <div className="text-center py-24 text-slate-500">
              <p>Belum ada data untuk ditampilkan.</p>
              <button onClick={() => goInput()} className="mt-3 text-emerald-400 hover:underline">Mulai input data →</button>
            </div>
          )
        )}
        {view === "input" && (
          <DailyInput month={month} initialTab={inputTab} readOnly={readOnly} missingToday={dash?.missing_today || []} onChanged={() => loadDash(month)} />
        )}
      </main>

      <OnboardingWizard key={ob.wizardKey} open={ob.showWizard} onComplete={ob.completeOnboarding} onSeed={ob.seedDemo}
        initial={ob.wizardInitial} onCancel={ob.cancelCopy} />
      <AiAnalysisPanel open={aiOpen} onClose={() => setAiOpen(false)} loading={aiLoading} result={aiResult} error={aiError} />
      <Toaster position="top-center" richColors />
    </div>
  );
}

export default App;
