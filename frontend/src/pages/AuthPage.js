import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";
import { formatApiErrorDetail } from "@/lib/api";
import { Logo } from "@/components/Navbar";

export default function AuthPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const { login, register, loginWithGoogle } = useAuth();
  const isRegister = location.pathname === "/register";
  const refCode = (params.get("ref") || "").toUpperCase();

  useEffect(() => {
    if (refCode) {
      try { sessionStorage.setItem("beatcut_ref", refCode); } catch {}
    }
  }, [refCode]);

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (isRegister) {
        await register(name, email, password, refCode || null);
        toast.success("Compte créé — bienvenue sur BEATCUT !");
      } else {
        await login(email, password);
        toast.success("Connecté !");
      }
      navigate("/dashboard");
    } catch (e) {
      setError(formatApiErrorDetail(e.response?.data?.detail) || e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <div className="p-6 flex items-center gap-3">
        <span className="rec-dot" />
        <Logo />
      </div>

      <div className="flex-1 flex items-center justify-center px-5 pb-16">
        <div className="w-full max-w-md">
          <div className="bg-card border border-border p-8 sm:p-10">
            <p className="font-osd text-xs tracking-[0.25em] text-primary mb-3">
              {isRegister ? "[ CRÉER UN COMPTE ]" : "[ CONNEXION ]"}
            </p>
            <h1 className="font-display text-2xl font-extrabold tracking-tight mb-7">
              {isRegister ? "Rejoins le studio." : "Content de te revoir."}
            </h1>
            {refCode && isRegister && (
              <div className="mb-5 border border-[#d9ffd0]/40 bg-[#d9ffd0]/5 px-4 py-3 font-osd text-[11px] tracking-wider text-[#d9ffd0]" data-testid="ref-banner">
                ✦ Parrainage actif : code <b>{refCode}</b> — +1 mois offert dès ton 1er paiement
              </div>
            )}

            <button
              onClick={loginWithGoogle}
              data-testid="google-login-button"
              className="w-full flex items-center justify-center gap-3 border border-border px-5 py-3 text-sm font-medium hover:border-foreground transition-colors"
            >
              <svg width="17" height="17" viewBox="0 0 48 48">
                <path fill="#FFC107" d="M43.6 20.1H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.9 1.2 8 3l5.7-5.7C34.3 6.1 29.4 4 24 4 13 4 4 13 4 24s9 20 20 20 20-9 20-20c0-1.3-.1-2.6-.4-3.9z"/>
                <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.6 15.1 18.9 12 24 12c3.1 0 5.9 1.2 8 3l5.7-5.7C34.3 6.1 29.4 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/>
                <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-8l-6.5 5C9.6 39.6 16.3 44 24 44z"/>
                <path fill="#1976D2" d="M43.6 20.1H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C36.9 39.2 44 34 44 24c0-1.3-.1-2.6-.4-3.9z"/>
              </svg>
              Continuer avec Google
            </button>

            <div className="flex items-center gap-3 my-6 text-xs text-muted-foreground">
              <span className="flex-1 h-px bg-border" /> ou par email <span className="flex-1 h-px bg-border" />
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              {isRegister && (
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Ton nom ou pseudo"
                  data-testid="auth-name-input"
                  className="w-full bg-background border border-border px-4 py-3 text-sm focus:border-[#d9ffd0] focus:outline-none transition-colors"
                />
              )}
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="ton@email.com"
                data-testid="auth-email-input"
                className="w-full bg-background border border-border px-4 py-3 text-sm focus:border-[#d9ffd0] focus:outline-none transition-colors"
              />
              <input
                type="password"
                required
                minLength={6}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={isRegister ? "Mot de passe (6 caractères min.)" : "Mot de passe"}
                data-testid="auth-password-input"
                className="w-full bg-background border border-border px-4 py-3 text-sm focus:border-[#d9ffd0] focus:outline-none transition-colors"
              />
              {!isRegister && (
                <div className="text-right">
                  <Link
                    to="/forgot-password"
                    data-testid="forgot-password-link"
                    className="text-xs text-muted-foreground hover:text-foreground underline underline-offset-4 transition-colors"
                  >
                    Mot de passe oublié ?
                  </Link>
                </div>
              )}
              {error && (
                <p className="text-sm text-primary" data-testid="auth-error-message">
                  ⚠ {error}
                </p>
              )}
              <button
                type="submit"
                disabled={loading}
                data-testid="auth-submit-button"
                className="w-full bg-primary text-white font-bold px-5 py-3.5 hover:bg-[#d32f2f] transition-colors disabled:opacity-50"
              >
                {loading ? "…" : isRegister ? "Créer mon compte" : "Se connecter"}
              </button>
            </form>

            <p className="mt-6 text-sm text-muted-foreground text-center">
              {isRegister ? (
                <>
                  Déjà un compte ?{" "}
                  <Link to="/login" className="text-foreground underline underline-offset-4" data-testid="auth-switch-login">
                    Se connecter
                  </Link>
                </>
              ) : (
                <>
                  Pas encore de compte ?{" "}
                  <Link to="/register" className="text-foreground underline underline-offset-4" data-testid="auth-switch-register">
                    Créer un compte
                  </Link>
                </>
              )}
            </p>
          </div>
          <p className="mt-5 font-osd text-[11px] text-muted-foreground text-center tracking-wider">
            GRATUIT POUR TOUJOURS • PRO 12,99 €/MOIS SANS ENGAGEMENT
          </p>
        </div>
      </div>
    </div>
  );
}
