import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

export default function AuthCallback() {
  const navigate = useNavigate();
  const { user, setUser } = useAuth();
  const hasProcessed = useRef(false);

  useEffect(() => {
    if (hasProcessed.current) return;
    hasProcessed.current = true;

    const processSession = async () => {
      const hash = window.location.hash;
      const match = hash.match(/session_id=([^&]+)/);
      if (!match) {
        navigate("/login", { replace: true });
        return;
      }
      try {
        const payload = { session_id: match[1] };
        try {
          const ref = sessionStorage.getItem("beatcut_ref");
          if (ref) {
            payload.ref_code = ref;
            sessionStorage.removeItem("beatcut_ref");
          }
        } catch {}
        const { data } = await api.post("/auth/google/session", payload);
        setUser(data);
        window.history.replaceState(null, "", window.location.pathname);
        navigate("/dashboard", { replace: true, state: { user: data } });
      } catch (e) {
        console.error("Échange session Google échoué", e);
        navigate("/login", { replace: true });
      }
    };
    processSession();
  }, [navigate, setUser]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="font-osd text-sm text-[#d9ffd0] animate-pulse" data-testid="auth-callback-loading">
        CONNEXION EN COURS…
      </div>
    </div>
  );
}
