import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Activity, LayoutDashboard, ListChecks, Plus, Sparkles, Download, FileText, FileSpreadsheet, CalendarRange, Settings } from "lucide-react";
import { statusBg, statusLabel } from "@/lib/format";
import { monthLabel } from "@/lib/export";
import { LicenseMenu } from "@/features/auth/LicenseMenu";

export const TopNavbar = ({ view, setView, company, overallStatus, onQuickAdd, onAi, months, month, onMonthChange, onExportCsv, onExportPdf, onEditCompany, license, user, readOnly, onLogout }) => (
  <header data-testid="top-navbar" className="sticky top-0 z-50 backdrop-blur-xl bg-slate-950/80 border-b border-slate-800">
    <div className="mx-auto max-w-7xl px-4 sm:px-6">
      <div className="flex h-16 items-center justify-between gap-4">
        <div className="flex items-center gap-3 min-w-0">
          <div className="grid place-items-center h-9 w-9 rounded-lg bg-emerald-500 text-slate-950">
            <Activity className="h-5 w-5" strokeWidth={2.5} />
          </div>
          <div className="min-w-0">
            <p className="font-heading font-extrabold leading-none tracking-tight">SAMPE</p>
            <button data-testid="navbar-company-edit" onClick={onEditCompany} title="Ubah nama perusahaan"
              className="group flex items-center gap-1 max-w-[180px] text-xs text-slate-400 hover:text-emerald-400 transition-colors">
              <span data-testid="navbar-company-name" className="truncate">{company || "Atur nama toko"}</span>
              <Settings className="h-3 w-3 shrink-0 opacity-60 group-hover:opacity-100" />
            </button>
          </div>
          {overallStatus && (
            <Badge data-testid="navbar-status-badge" variant="outline" className={`ml-2 hidden lg:inline-flex ${statusBg[overallStatus]}`}>
              {statusLabel[overallStatus]}
            </Badge>
          )}
        </div>

        <nav className="hidden md:flex items-center gap-1 rounded-full border border-slate-800 bg-slate-900/60 p-1">
          <button data-testid="nav-dashboard" onClick={() => setView("dashboard")} className={`inline-flex items-center gap-2 rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${view === "dashboard" ? "bg-emerald-500 text-slate-950" : "text-slate-300 hover:text-white"}`}>
            <LayoutDashboard className="h-4 w-4" /> Dashboard
          </button>
          <button data-testid="nav-input" onClick={() => setView("input")} className={`inline-flex items-center gap-2 rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${view === "input" ? "bg-emerald-500 text-slate-950" : "text-slate-300 hover:text-white"}`}>
            <ListChecks className="h-4 w-4" /> List KPI
          </button>
        </nav>

        <div className="flex items-center gap-2">
          {months?.length > 0 && (
            <Select value={month} onValueChange={onMonthChange}>
              <SelectTrigger data-testid="navbar-month-select" className="h-9 w-[150px] bg-slate-900/60 border-slate-700 hidden sm:flex">
                <CalendarRange className="h-4 w-4 text-emerald-400 mr-1 shrink-0" />
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {months.map((m) => (
                  <SelectItem key={m} value={m} data-testid={`month-option-${m}`}>{monthLabel(m)}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button data-testid="navbar-export-button" size="sm" variant="outline" className="border-slate-700 hidden sm:inline-flex">
                <Download className="h-4 w-4 mr-1" /> Export
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem data-testid="export-pdf" onClick={onExportPdf}><FileText className="h-4 w-4 mr-2 text-red-400" /> Laporan PDF</DropdownMenuItem>
              <DropdownMenuItem data-testid="export-csv" onClick={onExportCsv}><FileSpreadsheet className="h-4 w-4 mr-2 text-emerald-400" /> Data CSV</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          <Button data-testid="navbar-ai-button" onClick={onAi} disabled={readOnly} size="sm" variant="outline" className="border-amber-500/40 text-amber-400 hover:bg-amber-500/10 hidden sm:inline-flex">
            <Sparkles className="h-4 w-4 mr-1" /> Analisa AI
          </Button>
          <Button data-testid="navbar-quick-add" onClick={onQuickAdd} disabled={readOnly} size="sm" className="bg-emerald-500 hover:bg-emerald-600 text-slate-950 font-semibold">
            <Plus className="h-4 w-4 mr-1" /> Input
          </Button>
          <LicenseMenu license={license} user={user} onLogout={onLogout} />
        </div>
      </div>
      <nav className="flex md:hidden items-center gap-1 pb-2">
        <button data-testid="nav-dashboard-m" onClick={() => setView("dashboard")} className={`flex-1 rounded-lg px-3 py-1.5 text-sm font-medium ${view === "dashboard" ? "bg-emerald-500 text-slate-950" : "bg-slate-900 text-slate-300"}`}>Dashboard</button>
        <button data-testid="nav-input-m" onClick={() => setView("input")} className={`flex-1 rounded-lg px-3 py-1.5 text-sm font-medium ${view === "input" ? "bg-emerald-500 text-slate-950" : "bg-slate-900 text-slate-300"}`}>List KPI</button>
        {months?.length > 0 && (
          <Select value={month} onValueChange={onMonthChange}>
            <SelectTrigger data-testid="navbar-month-select-m" className="h-8 w-[130px] bg-slate-900 border-slate-700"><SelectValue /></SelectTrigger>
            <SelectContent>{months.map((m) => <SelectItem key={m} value={m}>{monthLabel(m)}</SelectItem>)}</SelectContent>
          </Select>
        )}
      </nav>
    </div>
  </header>
);
