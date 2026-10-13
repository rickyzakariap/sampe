import { Wand2 } from "lucide-react";
import { SCALES } from "./presets";

export const ScalePicker = ({ scale, onPick }) => (
  <div data-testid="wizard-scale-picker" className="space-y-2">
    <p className="text-xs text-slate-400">Belum yakin angkanya? Pilih skala toko untuk contoh angka wajar:</p>
    <div className="grid grid-cols-3 gap-2">
      {Object.entries(SCALES).map(([k, s]) => (
        <button type="button" key={k} data-testid={`wizard-scale-${k}`} onClick={() => onPick(k)}
          className={`rounded-lg border px-3 py-2 text-left transition-colors ${scale === k ? "border-emerald-500 bg-emerald-500/10" : "border-slate-700 bg-slate-900/60 hover:border-slate-500"}`}>
          <p className={`text-sm font-semibold ${scale === k ? "text-emerald-400" : "text-slate-200"}`}>{s.label}</p>
          <p className="text-[11px] text-slate-500">{s.hint}</p>
        </button>
      ))}
    </div>
  </div>
);

export const ExampleButton = ({ scale, onUse }) => (
  <button type="button" data-testid="wizard-use-example" onClick={onUse}
    className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/5 px-3 py-1 text-xs font-medium text-emerald-300 transition-colors hover:bg-emerald-500/15">
    <Wand2 className="h-3.5 w-3.5" /> Pakai contoh skala {SCALES[scale].label}
  </button>
);
