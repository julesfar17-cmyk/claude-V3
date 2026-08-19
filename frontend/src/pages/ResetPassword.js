import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import api, { formatApiErrorDetail } from "@/lib/api";
import { Logo } from "@/components/Navbar";

export default function ResetPassword() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const token = params.get("token") || "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    if (password !== confirm) {
      setError("Les deux mots de passe ne correspondent pas");
      return;
    }
    setLoading(true);
    try {
      await api.post("/auth/reset-password", { token, password });
      toast.success("Mot de passe mis à jour — connecte-toi !");
      navigate("/login");
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
            <p className="font-osd text-xs tracking-[0.25em] text-primary mb-3">[ NOUVEAU MOT DE PASSE ]</p>
            <h1 className="font-display text-2xl font-extrabold tracking-tight mb-6">Choisis-en un solide.</h1>

            {!token ? (
              <p className="text-sm text-primary" data-testid="reset-no-token">
                Lien invalide — refais une demande depuis{" "}
                <Link to="/forgot-password" className="underline underline-offset-4">mot de passe oublié</Link>.
              </p>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-4">
                <input
                  type="password"
                  required
                  minLength={6}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Nouveau mot de passe (6 caractères min.)"
                  data-testid="reset-password-input"
                  className="w-full bg-background border border-border px-4 py-3 text-sm focus:border-[#d9ffd0] focus:outline-none transition-colors"
                />
                <input
                  type="password"
                  required
                  minLength={6}
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  placeholder="Confirme le mot de passe"
                  data-testid="reset-confirm-input"
                  className="w-full bg-background border border-border px-4 py-3 text-sm focus:border-[#d9ffd0] focus:outline-none transition-colors"
                />
                {error && (
                  <p className="text-sm text-primary" data-testid="reset-error-message">{error}</p>
                )}
                <button
                  type="submit"
                  disabled={loading}
                  data-testid="reset-submit-button"
                  className="w-full bg-primary text-white font-bold px-5 py-3.5 hover:opacity-90 transition-colors disabled:opacity-50"
                >
                  {loading ? "…" : "Mettre à jour le mot de passe"}
                </button>
              </form>
            )}

            <p className="mt-6 text-sm text-muted-foreground text-center">
              <Link to="/login" className="text-foreground underline underline-offset-4" data-testid="reset-back-login">
                ← Retour à la connexion
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
