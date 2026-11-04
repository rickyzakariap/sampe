import { BrandWordmark } from "@/components/BrandLogo";
import { useEffect, useRef, useState } from "react";
import { api, errMsg, TOKEN_KEY } from "@/lib/api";

const POINTS = [
  "Masuk pakai akun Google, tanpa password tambahan",
  "Lisensi otomatis menempel ke Gmail yang kamu pakai saat beli di Lynk.id",
  "Data tiap toko terpisah dan hanya bisa dibuka pemilik akunnya",
];

export const AuthShell = ({ children }) => (
  <div className="sampe-auth min-h-screen bg-background text-foreground">
    <header className="sampe-auth-header"><BrandWordmark /></header>
    <main className="sampe-auth-layout">
      <section className="sampe-auth-intro">
        <p className="sampe-auth-eyebrow">Analisis KPI untuk seller & UMKM</p>
        <h1>KPI toko harian,<br />terukur tiap hari.</h1>
        <p>Pantau target, realisasi, dan perkembangan toko dalam satu tempat.</p>
        <ul>{POINTS.map((p) => <li key={p}>{p}</li>)}</ul>
      </section>
      <section className="sampe-auth-access" aria-label="Akses SAMPE">
        <div className="sampe-auth-content">{children}</div>
      </section>
    </main>
    <footer className="sampe-auth-footer">SAMPE · System Analytic Marketplace</footer>
  </div>
);

function DirectGoogleButton({ onAuthenticated }) {
  const buttonRef = useRef(null);
  const busyRef = useRef(false);
  const [status, setStatus] = useState('Menyiapkan login Google…');
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    const script = document.createElement('script');
    script.src = 'https://accounts.google.com/gsi/client';
    script.async = true;
    script.onload = async () => {
      try {
        const { nonce } = await api.googleDirectChallenge();
        if (!active || !buttonRef.current) return;
        window.google.accounts.id.initialize({
          client_id: process.env.REACT_APP_GOOGLE_CLIENT_ID,
          nonce,
          ux_mode: 'popup',
          error_callback: () => { if (active) setStatus('Login dibatalkan. Coba lagi.'); },
          callback: async ({ credential }) => {
            if (!active || !credential || busyRef.current) return;
            busyRef.current = true;
            setBusy(true); setStatus('Memproses login…');
            try {
              await api.googleDirectLogin(credential);
              localStorage.removeItem(TOKEN_KEY);
              setStatus('Login berhasil.');
              await onAuthenticated?.();
            } catch (error) {
              setStatus(errMsg(error, 'Login gagal. Muat ulang halaman lalu coba lagi.'));
            } finally { busyRef.current = false; if (active) setBusy(false); }
          },
        });
        window.google.accounts.id.renderButton(buttonRef.current, { type: 'standard', theme: 'outline', size: 'large', text: 'signin_with', width: 320 });
        setStatus('');
      } catch { if (active) setStatus('Login Google belum tersedia.'); }
    };
    script.onerror = () => { if (active) setStatus('Tidak dapat memuat login Google.'); };
    document.head.appendChild(script);
    return () => { active = false; script.remove(); };
  }, [onAuthenticated]);
  return <div aria-busy={busy}><div ref={buttonRef} hidden={busy} /><p role="status" className="text-sm text-slate-400">{status}</p></div>;
}

export const GoogleLogin = ({ onAuthenticated }) => {
  const authUrl = process.env.REACT_APP_AUTH_URL || "";
  const direct = process.env.REACT_APP_GOOGLE_DIRECT_AUTH === 'true';
  const login = () => {
    if (!authUrl) return;
    const redirectUrl = window.location.origin + "/";
    const url = new URL(authUrl);
    if (url.protocol !== "https:") return;
    url.searchParams.set("redirect", redirectUrl);
    window.location.assign(url.toString());
  };
  return (
    <AuthShell>
      <div data-testid="google-login-page">
        <h2 className="mt-2 text-2xl font-extrabold tracking-tight">Masuk ke SAMPE</h2>
        <p className="mt-1 text-sm text-slate-400">Gunakan Gmail yang sama dengan email saat membeli lisensi di Lynk.id.</p>
      </div>
      {direct ? (process.env.REACT_APP_GOOGLE_CLIENT_ID ? <DirectGoogleButton onAuthenticated={onAuthenticated} /> : <p role="alert">Login Google belum dikonfigurasi.</p>) : <><button data-testid="google-login-button" onClick={login} disabled={!authUrl}
        className="flex w-full items-center justify-center gap-3 rounded-lg bg-white h-12 text-sm font-semibold text-slate-900 transition-transform hover:-translate-y-0.5">
        <svg viewBox="0 0 48 48" className="h-5 w-5"><path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.2-.1-2.3-.4-3.5z"/><path fill="#FF3D00" d="m6.3 14.7 6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/><path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z"/><path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.2-.1-2.3-.4-3.5z"/></svg>
        Masuk dengan Google
      </button>
      {!authUrl && <p className="mt-2 text-xs text-amber-300">Login Google belum dikonfigurasi.</p>}</>}
      <p className="text-xs text-slate-500">Sudah bayar tapi belum dapat kode? Buka <a href="/aktivasi" data-testid="login-activation-link" className="text-emerald-400 hover:underline">halaman aktivasi</a>.</p>
    </AuthShell>
  );
};
