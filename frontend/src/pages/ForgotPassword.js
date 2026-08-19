import { useState } from "react";
import { Link } from "react-router-dom";
import api, { formatApiErrorDetail } from "@/lib/api";
import { Logo } from "@/components/Navbar";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [devLink, setDevLink] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const { data } = await api.post("/auth/forgot-password", {
        email,
        origin_url: window.location.origin,
      });
      setSent(true);
      if (data.dev_reset_link) setDevLink(data.dev_reset_link);
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
            <p className="font-osd text-xs tracking-[0.25em] text-primary mb-3">[ MOT DE PASSE OUBLIÉ ]</p>
            <h1 className="font-display text-2xl font-extrabold tracking-tight mb-4">Pas de panique.</h1>

            {!sent ? (
              <>
                <p className="text-sm text-muted-foreground mb-6">
                  Entre ton email : on t'envoie un lien pour réinitialiser ton mot de passe (valable 1 heure).
                </p>
                <form onSubmit={handleSubmit} className="space-y-4">
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="ton@email.com"
                    data-testid="forgot-email-input"
                    className="w-full bg-background border border-border px-4 py-3 text-sm focus:border-[#d9ffd0] focus:outline-none transition-colors"
                  />
                  {error && (
                    <p className="text-sm text-primary" data-testid="forgot-error-message">⚠ {error}</p>
                  )}
                  <button
                    type="submit"
                    disabled={loading}
                    data-testid="forgot-submit-button"
                    className="w-full bg-primary text-white font-bold px-5 py-3.5 hover:opacity-90 transition-colors disabled:opacity-50"
                  >
                    {loading ? "…" : "Envoyer le lien"}
                  </button>
                </form>
              </>
            ) : (
              <div data-testid="forgot-success-message">
                <p className="text-sm text-foreground leading-relaxed">
                  ✓ Si un compte existe avec <b>{email}</b>, un lien de réinitialisation a été envoyé.
                </p>
                {devLink && (
                  <div className="mt-5 border border-[#d9ffd0]/40 bg-[#d9ffd0]/5 p-4">
                    <p className="font-osd text-[11px] tracking-wider text-[#d9ffd0] mb-2">
                      MODE DÉMO — EMAILS PAS ENCORE ACTIVÉS
                    </p>
                    <p className="text-xs text-muted-foreground mb-3">
                      En attendant la configuration du domaine d'envoi, voici ton lien :
                    </p>
                    <a
                      href={devLink}
                      data-testid="dev-reset-link"
                      className="text-sm text-[#d9ffd0] underline underline-offset-4 break-all"
                    >
                      Réinitialiser mon mot de passe →
                    </a>
                  </div>
                )}
              </div>
            )}

            <p className="mt-6 text-sm text-muted-foreground text-center">
              <Link to="/login" className="text-foreground underline underline-offset-4" data-testid="forgot-back-login">
                ← Retour à la connexion
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
