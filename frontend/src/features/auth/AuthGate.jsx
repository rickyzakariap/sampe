import { useCallback, useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { api, TOKEN_KEY } from "@/lib/api";
import { GoogleLogin } from "./GoogleLogin";
import { ClaimLicense } from "./ClaimLicense";
import { queryClient } from "@/lib/queryClient";
import { toast } from "sonner";

const Splash = () => (
  <div className="min-h-screen grid place-items-center bg-background text-slate-400">
    <Loader2 className="h-8 w-8 animate-spin text-emerald-400" />
  </div>
);

export const AuthGate = ({ children }) => {
  const [session, setSession] = useState(undefined);

  const check = useCallback(async () => {
    try { setSession(await api.me()); } catch { setSession(null); }
  }, []);

  useEffect(() => { check(); }, [check]);
  useEffect(() => {
    const out = () => setSession(null);
    window.addEventListener("pulse:logout", out);
    return () => window.removeEventListener("pulse:logout", out);
  }, []);

  const logout = async () => {
    try {
      await api.logout();
      localStorage.removeItem(TOKEN_KEY);
      queryClient.clear();
      setSession(null);
    } catch {
      toast.error("Gagal keluar. Coba lagi.");
    }
  };

  if (session === undefined) return <Splash />;
  if (!session) return <GoogleLogin />;
  if (!session.license || session.license.status === "revoked") {
    return <ClaimLicense user={session.user} license={session.license} renewUrl={session.renew_url} onClaimed={check} onLogout={logout} />;
  }
  return children({ license: session.license, writable: session.writable, renewUrl: session.renew_url, user: session.user, logout });
};
