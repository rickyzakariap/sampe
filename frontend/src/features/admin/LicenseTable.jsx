import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Copy, CalendarPlus, Ban, RotateCcw } from "lucide-react";
import { DURATIONS, copyText } from "./CreateLicenseForm";

const STATUS = {
  active: ["Aktif", "text-emerald-400 border-emerald-500/30 bg-emerald-500/10"],
  unused: ["Belum dipakai", "text-sky-400 border-sky-500/30 bg-sky-500/10"],
  expired: ["Habis (read-only)", "text-amber-400 border-amber-500/30 bg-amber-500/10"],
  revoked: ["Dicabut", "text-red-400 border-red-500/30 bg-red-500/10"],
};

const fmt = (s) => (s ? new Date(s).toLocaleString("id-ID", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "—");

const daysLeft = (r) => {
  if (r.status === "unused") return `${r.duration_days} hari (belum mulai)`;
  if (!r.expires_at) return "—";
  const d = Math.ceil((new Date(r.expires_at) - Date.now()) / 86400000);
  return d > 0 ? `${d} hari lagi` : `lewat ${Math.abs(d)} hari`;
};

const Row = ({ r, onExtend, onRevoke, onRestore }) => (
  <tr data-testid={`admin-license-row-${r.code}`} className="border-b border-slate-800/60 last:border-0 hover:bg-slate-800/30 align-top">
    <td className="py-3 pr-3">
      <p className="font-medium text-slate-200">{r.label}</p>
      <p className="text-xs text-slate-500">{r.company_name ? `Toko: ${r.company_name}` : "Belum setup KPI"} · {r.entry_count} entri</p>
      <p data-testid={`admin-license-email-${r.code}`} className="text-xs text-slate-500">
        {r.google_email ? `Google: ${r.google_email}` : r.email ? `Email: ${r.email} (belum login)` : "Belum terhubung ke akun"}
        {r.source === "lynk" && <span className="ml-1.5 rounded bg-amber-500/15 px-1.5 text-[10px] font-semibold text-amber-400">LYNK</span>}
      </p>
    </td>
    <td className="py-3 px-3">
      <button data-testid={`admin-copy-code-${r.code}`} onClick={() => copyText(r.code)} className="num inline-flex items-center gap-1.5 text-xs tracking-wider text-slate-300 hover:text-emerald-400">
        {r.code} <Copy className="h-3 w-3" />
      </button>
    </td>
    <td className="py-3 px-3"><Badge data-testid={`admin-status-${r.code}`} variant="outline" className={STATUS[r.status][1]}>{STATUS[r.status][0]}</Badge></td>
    <td className="num py-3 px-3 text-xs text-slate-300">{daysLeft(r)}<p className="text-slate-500">s/d {fmt(r.expires_at)}</p></td>
    <td className="num py-3 px-3 text-xs text-slate-400">{fmt(r.last_login_at)}</td>
    <td className="py-3 pl-3">
      <div className="flex justify-end gap-2">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button data-testid={`admin-extend-${r.code}`} size="sm" variant="outline" className="border-slate-700"><CalendarPlus className="h-4 w-4 mr-1" /> Perpanjang</Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            {DURATIONS.map(([d, l]) => (
              <DropdownMenuItem key={d} data-testid={`admin-extend-${r.code}-${d}`} onClick={() => onExtend(r, d)}>+ {l}</DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
        {r.revoked ? (
          <Button data-testid={`admin-restore-${r.code}`} size="sm" variant="outline" className="border-emerald-500/40 text-emerald-300" onClick={() => onRestore(r)}><RotateCcw className="h-4 w-4 mr-1" /> Pulihkan</Button>
        ) : (
          <Button data-testid={`admin-revoke-${r.code}`} size="sm" variant="outline" className="border-red-500/40 text-red-300 hover:bg-red-500/10"
            onClick={() => window.confirm(`Cabut lisensi ${r.label}? User langsung tidak bisa masuk.`) && onRevoke(r)}><Ban className="h-4 w-4 mr-1" /> Cabut</Button>
        )}
      </div>
    </td>
  </tr>
);

export const LicenseTable = ({ rows, ...actions }) => (
  <div data-testid="admin-license-table" className="overflow-x-auto rounded-xl border border-slate-800 bg-[#161F30]">
    {rows.length === 0 ? <p className="py-16 text-center text-sm text-slate-500">Belum ada lisensi. Buat lisensi pertama di atas.</p> : (
      <table className="w-full min-w-[860px] text-sm">
        <thead>
          <tr className="border-b border-slate-800 text-left text-xs uppercase tracking-wider text-slate-500">
            {["User / Toko", "Kode Lisensi", "Status", "Masa Aktif", "Login Terakhir", ""].map((h) => <th key={h} className="px-3 py-3 font-semibold first:pl-4">{h}</th>)}
          </tr>
        </thead>
        <tbody className="[&_td:first-child]:pl-4 [&_td:last-child]:pr-4">
          {rows.map((r) => <Row key={r.id} r={r} {...actions} />)}
        </tbody>
      </table>
    )}
  </div>
);
