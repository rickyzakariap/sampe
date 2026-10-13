import { useState, useCallback } from "react";
import { toast } from "sonner";
import { api, currentMonth, shiftMonth, errMsg } from "@/lib/api";

// User flow & onboarding: boot config, setup KPI, demo, ubah nama, setup ulang.
export const useOnboarding = ({ onReady, onCleared, readOnly }) => {
  const [config, setConfig] = useState(null);
  const [showWizard, setShowWizard] = useState(false);
  const [wizardKey, setWizardKey] = useState(0);
  const [wizardInitial, setWizardInitial] = useState(null);

  const startCopy = (toMonth) => {
    const src = config;
    if (!src) return;
    const fields = ["company_name", "target_sales", "budget_ads", "budget_branding", "budget_campaign", "budget_kol",
      "target_kol_count", "live_team_count", "target_live_hours", "target_live_revenue"];
    setWizardInitial({ ...Object.fromEntries(fields.map((k) => [k, src[k] ?? ""])), month: toMonth || shiftMonth(src.month, 1) });
    setWizardKey((k) => k + 1);
    setShowWizard(true);
  };

  const cancelCopy = () => { setShowWizard(false); setWizardInitial(null); };

  const boot = useCallback(async () => {
    const cfg = await api.getConfig();
    setConfig(cfg);
    if (cfg) await onReady(cfg.month < currentMonth() ? currentMonth() : cfg.month);
    else if (!readOnly) setShowWizard(true);
  }, [onReady, readOnly]);

  const completeOnboarding = async (payload) => {
    let cfg;
    try { cfg = await api.saveConfig(payload); } catch (e) { toast.error(errMsg(e, "Gagal menyimpan target")); return; }
    setConfig(await api.getConfig());
    setShowWizard(false);
    const copied = Boolean(wizardInitial);
    setWizardInitial(null);
    await onReady(cfg.month);
    toast.success(copied ? `Target ${cfg.month} tersimpan` : "KPI berhasil di-setup!");
  };

  const seedDemo = async (name) => {
    toast.loading("Menyiapkan data demo…", { id: "seed" });
    let res;
    try { res = await api.seed(name); } catch (e) { toast.dismiss("seed"); toast.error(errMsg(e)); return; }
    toast.dismiss("seed");
    setConfig(await api.getConfig());
    setShowWizard(false);
    await onReady(res.month);
    toast.success("Data demo siap!");
  };

  const saveCompany = async (name) => {
    try {
      setConfig(await api.updateCompany(name));
      await onReady(config?.month);
      toast.success("Nama perusahaan diperbarui");
    } catch (e) {
      toast.error(errMsg(e, "Gagal menyimpan nama perusahaan"));
      throw new Error("save failed");
    }
  };

  const resetAll = async () => {
    try { await api.reset(); } catch (e) { toast.error(errMsg(e)); return; }
    setConfig(null);
    onCleared();
    setWizardInitial(null);
    setWizardKey((k) => k + 1);
    setShowWizard(true);
    toast.success("Semua data dikosongkan. Silakan setup KPI dari awal.");
  };

  return { config, showWizard, wizardKey, wizardInitial, boot, completeOnboarding, seedDemo, saveCompany, resetAll, startCopy, cancelCopy };
};
