import { CalendarPlus, Copy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { monthLabel } from "@/lib/export";

export const CopyTargetReminder = ({ month, fromMonth, onCopy }) => (
  <div data-testid="copy-target-reminder" className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-4">
    <div className="flex items-start gap-3">
      <CalendarPlus className="mt-0.5 h-5 w-5 shrink-0 text-emerald-400" />
      <div>
        <p className="text-sm font-semibold text-emerald-300">{monthLabel(month)} belum punya target sendiri</p>
        <p className="text-xs text-slate-400">Dashboard sementara memakai target {monthLabel(fromMonth)}. Salin lalu sesuaikan angkanya, tanpa setup dari nol.</p>
      </div>
    </div>
    <Button data-testid="copy-target-reminder-button" size="sm" onClick={() => onCopy(month)} className="bg-emerald-500 hover:bg-emerald-600 text-slate-950 font-semibold">
      <Copy className="h-4 w-4 mr-1" /> Salin Target {monthLabel(fromMonth)}
    </Button>
  </div>
);
