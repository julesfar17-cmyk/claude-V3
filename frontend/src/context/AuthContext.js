import { createContext, useCallback, useContext, useEffect, useState } from "react";
import api from "@/lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  // undefined = vérification en cours, null = non connecté, objet = connecté
  const [user, setUser] = useState(undefined);

  const checkAuth = useCallback(async () => {
    try {
      const { data } = await api.get("/auth/me");
      setUser(data);
    } catch {
      setUser(null);
    }
  }, []);

  useEffect(() => {
    // CRITICAL : si on revient du callback OAuth, AuthCallback gère l'échange d'abord
    if (window.location.hash?.includes("session_id=")) return;
    checkAuth();
  }, [checkAuth]);

  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    setUser(data);
    return data;
  };

  const register = async (name, email, password, refCode = null) => {
    const payload = { name, email, password };
    if (refCode) payload.ref_code = refCode;
    const { data } = await api.post("/auth/register", payload);
    setUser(data);
    return data;
  };

  const loginWithGoogle = () => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    let redirectUrl = window.location.origin + "/dashboard";
    try {
      const ref = sessionStorage.getItem("beatcut_ref");
      if (ref) redirectUrl += `?ref=${encodeURIComponent(ref)}`;
    } catch {}
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  const logout = async () => {
    try {
      await api.post("/auth/logout");
    } catch {
      // ignore
    }
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, setUser, login, register, loginWithGoogle, logout, refreshUser: checkAuth }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
