import { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2, RotateCcw, AlertTriangle, Copy } from "lucide-react";
import { TargetHistory } from "./TargetHistory";

const ResetZone = ({ onReset, onDone }) => {
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const run = async () => {
    setBusy(true);
    try { await onReset(); onDone(); } finally { setBusy(false); setConfirm(false); }
  };
  return (
    <div data-testid="settings-reset-zone" className="rounded-lg border border-red-500/25 bg-red-500/5 p-4">
      <p className="text-sm font-semibold text-red-300">Setup Ulang KPI</p>
      <p className="mt-1 text-xs text-slate-400">Menghapus semua target, budget, dan data input harian. Kamu akan kembali ke onboarding langkah 1.</p>
      {!confirm ? (
        <Button data-testid="settings-reset-button" type="button" variant="outline" size="sm" onClick={() => setConfirm(true)}
          className="mt-3 border-red-500/40 text-red-300 hover:bg-red-500/10">
          <RotateCcw className="h-4 w-4 mr-1" /> Setup Ulang KPI
        </Button>
      ) : (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="flex items-center gap-1 text-xs text-red-300"><AlertTriangle className="h-3.5 w-3.5" /> Yakin? Data tidak bisa dikembalikan.</span>
          <Button data-testid="settings-reset-confirm" type="button" size="sm" disabled={busy} onClick={run} className="bg-red-500 hover:bg-red-600 text-white">
            {busy && <Loader2 className="h-4 w-4 mr-1 animate-spin" />} Ya, hapus semua
          </Button>
          <Button data-testid="settings-reset-cancel" type="button" size="sm" variant="ghost" onClick={() => setConfirm(false)}>Batal</Button>
        </div>
      )}
    </div>
  );
};

export const SettingsDialog = ({ open, onClose, current, onSave, onReset, onCopyNext, nextMonthLabel, readOnly }) => {
  const [name, setName] = useState(current || "");
  const [saving, setSaving] = useState(false);

  useEffect(() => { if (open) setName(current || ""); }, [open, current]);

  const submit = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    try { await onSave(name.trim()); onClose(); } finally { setSaving(false); }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent data-testid="company-edit-dialog" className="bg-slate-950 border-slate-800 sm:max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Pengaturan Toko</DialogTitle>
          <DialogDescription className="text-slate-400">Nama ini tampil di navbar, laporan PDF, dan analisa AI.</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="company-name">Nama Perusahaan / Toko</Label>
            <Input id="company-name" data-testid="company-name-input" value={name} maxLength={80}
              onChange={(e) => setName(e.target.value)} placeholder="Ketik nama toko kamu" className="bg-slate-900 border-slate-700" />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" className="border-slate-700" onClick={onClose} data-testid="company-cancel-button">Batal</Button>
            <Button type="submit" disabled={readOnly || saving || !name.trim()} data-testid="company-save-button" className="bg-emerald-500 hover:bg-emerald-600 text-slate-950 font-semibold">
              {saving && <Loader2 className="h-4 w-4 mr-1 animate-spin" />} Simpan
            </Button>
          </DialogFooter>
        </form>
        <div className="space-y-2">
          <p className="text-sm font-semibold text-slate-200">Riwayat Target</p>
          <p className="text-xs text-slate-500">Target & budget tiap bulan, dengan % naik/turun dibanding bulan sebelumnya.</p>
          <TargetHistory open={open} />
        </div>
        {!readOnly && (<>
        <div data-testid="settings-copy-zone" className="rounded-lg border border-emerald-500/25 bg-emerald-500/5 p-4">
          <p className="text-sm font-semibold text-emerald-300">Target Bulan Berikutnya</p>
          <p className="mt-1 text-xs text-slate-400">Salin semua target & budget ke {nextMonthLabel}. Kamu bisa cek dan ubah angkanya sebelum disimpan.</p>
          <Button data-testid="settings-copy-next-button" type="button" size="sm" onClick={() => { onClose(); onCopyNext(); }}
            className="mt-3 bg-emerald-500 hover:bg-emerald-600 text-slate-950 font-semibold">
            <Copy className="h-4 w-4 mr-1" /> Salin Target ke {nextMonthLabel}
          </Button>
        </div>
        <ResetZone onReset={onReset} onDone={onClose} />
        </>)}
      </DialogContent>
    </Dialog>
  );
};
