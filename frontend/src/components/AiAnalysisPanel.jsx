import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";
import { AlertTriangle, Loader2 } from "lucide-react";
import { AiMarkdown } from "@/components/AiMarkdown";
import { motion, useReducedMotion } from "framer-motion";

export const AiAnalysisPanel = ({ open, onClose, loading, result, error }) => {
  const reduceMotion = useReducedMotion();
  const reveal = {
    initial: reduceMotion ? false : { opacity: 0, y: 8 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: reduceMotion ? 0 : 0.18, ease: "easeOut" },
  };

  return (
  <Sheet open={open} onOpenChange={(o) => !o && onClose()}>
    <SheetContent data-testid="ai-analysis-panel" aria-busy={loading} className="ai-analysis-panel w-full sm:max-w-lg bg-slate-950 border-slate-800 overflow-y-auto">
      <SheetHeader className="space-y-1">
        <SheetTitle className="pr-8 text-xl font-semibold">Analisa AI KPI</SheetTitle>
        <p className="text-sm leading-relaxed text-slate-400">Rekomendasi untuk mengejar target sisa bulan ini.</p>
      </SheetHeader>

      <div className="mt-6 space-y-5">
        {loading && (
          <motion.div key="loading" {...reveal} role="status" aria-live="polite" className="flex flex-col items-center justify-center gap-3 py-20 text-slate-400">
            <Loader2 className="h-8 w-8 motion-safe:animate-spin text-emerald-400" />
            <p className="text-sm">AI sedang menganalisa data harianmu…</p>
          </motion.div>
        )}

        {error && !loading && (
          <motion.div key="error" {...reveal} role="alert" className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-300">{error}</motion.div>
        )}

        {!loading && result && (
          <motion.div key="result" {...reveal} className="space-y-5">
            {result.reds?.length > 0 && (
              <div className="rounded-xl border border-red-500/25 bg-red-500/5 p-4">
                <div className="flex items-center gap-2 text-red-400 mb-2">
                  <AlertTriangle className="h-4 w-4" />
                  <span className="text-sm font-semibold">KPI tertinggal ({result.reds.length})</span>
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
            <p className="text-xs text-slate-400">Dihasilkan oleh GPT · {new Date(result.generated_at).toLocaleString("id-ID")}</p>
          </motion.div>
        )}
      </div>
    </SheetContent>
  </Sheet>
  );
};
