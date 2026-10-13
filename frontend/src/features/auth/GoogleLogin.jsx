import { Activity, ShieldCheck } from "lucide-react";

const POINTS = [
  "Masuk pakai akun Google, tanpa password tambahan",
  "Lisensi otomatis menempel ke Gmail yang kamu pakai saat beli di Lynk.id",
  "Data tiap toko terpisah dan hanya bisa dibuka pemilik akunnya",
];

export const AuthShell = ({ children }) => (
  <div className="min-h-screen bg-background text-foreground grid lg:grid-cols-[1.1fr_1fr]">
    <section className="hidden lg:flex flex-col justify-between border-r border-slate-800 bg-[#0d1424] p-12">
      <div className="flex items-center gap-3">
        <div className="grid place-items-center h-10 w-10 rounded-lg bg-emerald-500 text-slate-950"><Activity className="h-5 w-5" strokeWidth={2.5} /></div>
        <div>
          <p className="font-heading text-lg font-extrabold leading-none tracking-tight">SAMPE</p>
          <p className="text-[11px] text-slate-500">System Analytic Marketplace</p>
        </div>
      </div>
      <div className="max-w-md space-y-6 animate-fade-up">
        <h1 className="text-4xl xl:text-5xl font-extrabold leading-tight tracking-tight">KPI toko harian, <span className="text-emerald-400">terukur tiap hari.</span></h1>
        <ul className="space-y-3">
          {POINTS.map((p) => <li key={p} className="flex gap-3 text-sm text-slate-300"><ShieldCheck className="h-5 w-5 shrink-0 text-emerald-400" />{p}</li>)}
        </ul>
      </div>
      <p className="text-xs text-slate-600">Reporting & KPI Analytics untuk Seller Marketplace & UMKM Indonesia</p>
    </section>
    <section className="flex items-center justify-center p-6">
      <div className="w-full max-w-sm space-y-6 animate-fade-up">{children}</div>
    </section>
  </div>
);

export const GoogleLogin = () => {
  const login = () => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    const redirectUrl = window.location.origin + "/";
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };
  return (
    <AuthShell>
      <div data-testid="google-login-page">
        <p className="text-xs font-semibold uppercase tracking-widest text-emerald-400 lg:hidden">SAMPE · System Analytic Marketplace</p>
        <h2 className="mt-2 text-2xl font-extrabold tracking-tight">Masuk ke SAMPE</h2>
        <p className="mt-1 text-sm text-slate-400">Gunakan Gmail yang sama dengan email saat membeli lisensi di Lynk.id.</p>
      </div>
      <button data-testid="google-login-button" onClick={login}
        className="flex w-full items-center justify-center gap-3 rounded-lg bg-white h-12 text-sm font-semibold text-slate-900 transition-transform hover:-translate-y-0.5">
        <svg viewBox="0 0 48 48" className="h-5 w-5"><path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.2-.1-2.3-.4-3.5z"/><path fill="#FF3D00" d="m6.3 14.7 6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/><path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z"/><path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.2-.1-2.3-.4-3.5z"/></svg>
        Masuk dengan Google
      </button>
      <p className="text-xs text-slate-500">Sudah bayar tapi belum dapat kode? Buka <a href="/aktivasi" data-testid="login-activation-link" className="text-emerald-400 hover:underline">halaman aktivasi</a>.</p>
    </AuthShell>
  );
};
