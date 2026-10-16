import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";
import { Sparkles, AlertTriangle, Loader2 } from "lucide-react";
import { AiMarkdown } from "@/components/AiMarkdown";

export const AiAnalysisPanel = ({ open, onClose, loading, result, error }) => (
  <Sheet open={open} onOpenChange={(o) => !o && onClose()}>
    <SheetContent data-testid="ai-analysis-panel" aria-busy={loading} className="ai-analysis-panel w-full sm:max-w-lg bg-slate-950 border-slate-800 overflow-y-auto">
      <SheetHeader className="space-y-1">
        <SheetTitle className="flex items-center gap-2 text-xl">
          <span className="grid place-items-center h-8 w-8 rounded-lg bg-amber-500/15 border border-amber-500/30">
            <Sparkles className={`h-4 w-4 text-amber-400 ${loading ? "motion-safe:animate-pulse" : ""}`} />
          </span>
          Analisa AI KPI
        </SheetTitle>
        <p className="text-sm text-slate-400">Rekomendasi actionable untuk mengejar target sisa bulan ini.</p>
      </SheetHeader>

      <div className="mt-6 space-y-5">
        {loading && (
          <div role="status" aria-live="polite" className="flex flex-col items-center justify-center gap-3 py-20 text-slate-400">
            <Loader2 className="h-8 w-8 motion-safe:animate-spin text-emerald-400" />
            <p className="text-sm">AI sedang menganalisa data harianmu…</p>
          </div>
        )}

        {error && !loading && (
          <div role="alert" className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-300">{error}</div>
        )}

        {!loading && result && (
          <>
            {result.reds?.length > 0 && (
              <div className="rounded-xl border border-red-500/25 bg-red-500/5 p-4">
                <div className="flex items-center gap-2 text-red-400 mb-2">
                  <AlertTriangle className="h-4 w-4" />
                  <span className="text-xs font-semibold uppercase tracking-wider">KPI Tertinggal ({result.reds.length})</span>
                </div>
                <ul className="space-y-1.5">
                  {result.reds.map((r, i) => (
                    <li key={i} className="text-xs text-slate-300 leading-relaxed">• {r}</li>
                  ))}
                </ul>
              </div>
            )}

            <div data-testid="ai-analysis-recommendations-list" className="rounded-xl border border-slate-800 bg-[#161F30] p-5">
              <Badge variant="outline" className="mb-3 bg-emerald-500/10 border-emerald-500/30 text-emerald-400">Rekomendasi AI</Badge>
              <AiMarkdown text={result.analysis} />
            </div>
            <p className="text-center text-xs text-slate-600">Dihasilkan oleh GPT · {new Date(result.generated_at).toLocaleString("id-ID")}</p>
          </>
        )}
      </div>
    </SheetContent>
  </Sheet>
);
