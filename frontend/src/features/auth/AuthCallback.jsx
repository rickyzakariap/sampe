import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { api, TOKEN_KEY } from "@/lib/api";

export const AuthCallback = () => {
  const done = useRef(false);
  const navigate = useNavigate();
  useEffect(() => {
    if (done.current) return;
    done.current = true;
    const sid = new URLSearchParams(window.location.hash.slice(1)).get("session_id");
    api.googleSession(sid)
      .then((r) => localStorage.setItem(TOKEN_KEY, r.session_token))
      .catch(() => localStorage.removeItem(TOKEN_KEY))
      .finally(() => navigate("/", { replace: true }));
  }, [navigate]);
  return (
    <div className="min-h-screen grid place-items-center bg-background text-slate-400">
      <Loader2 className="h-8 w-8 animate-spin text-emerald-400" />
    </div>
  );
};
