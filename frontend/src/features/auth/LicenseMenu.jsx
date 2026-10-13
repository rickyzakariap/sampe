import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { KeyRound, LogOut } from "lucide-react";

export const daysLeft = (lic) => (lic?.expires_at ? Math.ceil((new Date(lic.expires_at) - Date.now()) / 86400000) : null);

export const LicenseMenu = ({ license, user, onLogout }) => {
  if (!license) return null;
  const left = daysLeft(license);
  const expired = license.status === "expired";
  const tone = expired ? "text-red-400 border-red-500/40" : left <= 3 ? "text-amber-400 border-amber-500/40" : "text-slate-300 border-slate-700";
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button data-testid="navbar-license-menu" size="sm" variant="outline" className={`num ${tone}`}>
          <KeyRound className="h-4 w-4 sm:mr-1" /><span className="hidden sm:inline">{expired ? "Habis" : `${left} hari`}</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64">
        <DropdownMenuLabel className="space-y-1">
          {user && <p data-testid="license-menu-email" className="truncate text-xs font-normal text-slate-300">{user.email}</p>}
          <p className="text-xs text-slate-400">Lisensi</p>
          <p data-testid="license-menu-code" className="num text-sm tracking-wider">{license.code}</p>
          <p data-testid="license-menu-expiry" className="text-xs font-normal text-slate-400">
            {expired ? "Sudah habis" : `Berlaku ${left} hari lagi`} · s/d {new Date(license.expires_at).toLocaleDateString("id-ID", { day: "2-digit", month: "short", year: "numeric" })}
          </p>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem data-testid="navbar-logout" onClick={onLogout} className="text-red-400"><LogOut className="h-4 w-4 mr-2" /> Keluar</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

const RenewLink = ({ url, testid }) => url ? (
  <a data-testid={testid} href={url} target="_blank" rel="noreferrer"
    className="ml-2 inline-flex items-center rounded-full bg-white/10 px-3 py-1 text-xs font-semibold text-white hover:bg-white/20">Perpanjang di Lynk</a>
) : null;

export const ReadOnlyBanner = ({ renewUrl }) => (
  <div data-testid="license-expired-banner" className="border-b border-red-500/30 bg-red-500/10 px-4 py-2.5 text-center text-sm text-red-200">
    Lisensi kamu sudah habis. Data tetap aman dan bisa dilihat, tapi input & perubahan dikunci.
    <RenewLink url={renewUrl} testid="expired-renew-link" />
  </div>
);

export const RenewSoonBanner = ({ license, renewUrl }) => {
  const left = daysLeft(license);
  if (license.status !== "active" || left == null || left > 3) return null;
  return (
    <div data-testid="license-renew-soon-banner" className="border-b border-amber-500/30 bg-amber-500/10 px-4 py-2.5 text-center text-sm text-amber-200">
      Lisensi kamu habis dalam <b className="num">{left} hari</b>. Perpanjang sekarang dengan email yang sama — sisa hari tetap terhitung.
      <RenewLink url={renewUrl} testid="renew-soon-link" />
    </div>
  );
};
