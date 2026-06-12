import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { Clapperboard, Crown, BadgeCheck, CalendarClock, ArrowRight } from "lucide-react";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import { useAuth } from "@/context/AuthContext";
import api, { formatApiErrorDetail } from "@/lib/api";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";

const fmtDate = (iso) =>
  iso ? new Date(iso).toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" }) : "";

export default function Dashboard() {
  const { user, refreshUser } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const sessionId = params.get("session_id");
  const highlight = params.get("upgrade") === "1";
  const [checkingPayment, setCheckingPayment] = useState(!!sessionId);
  const [busy, setBusy] = useState(false);
  const pollRef = useRef(false);

  const sub = user?.subscription || {};
  const isPro = !!user?.is_pro;
  const canceled = !!sub.cancel_at_period_end;

  // Vérification du paiement au retour de Stripe
  useEffect(() => {
    if (!sessionId || pollRef.current) return;
    pollRef.current = true;
    let attempts = 0;
    const poll = async () => {
      if (attempts >= 8) {
        setCheckingPayment(false);
        toast.error("Vérification du paiement expirée — réessaie dans une minute.");
        return;
      }
      attempts++;
      try {
        const { data } = await api.get(`/payments/status/${sessionId}`);
        if (data.payment_status === "paid") {
          await refreshUser();
          setCheckingPayment(false);
          toast.success("Paiement confirmé — bienvenue en PRO ! 🎉");
          navigate("/dashboard", { replace: true });
          return;
        }
        if (data.status === "expired") {
          setCheckingPayment(false);
          toast.error("La session de paiement a expiré. Réessaie.");
          return;
        }
        setTimeout(poll, 2000);
      } catch {
        setCheckingPayment(false);
        toast.error("Impossible de vérifier le paiement.");
      }
    };
    poll();
  }, [sessionId, refreshUser, navigate]);

  const startCheckout = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/payments/checkout", { origin_url: window.location.origin });
      window.location.href = data.url;
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail) || "Erreur lors de la création du paiement");
      setBusy(false);
    }
  };

  const cancelSubscription = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/subscription/cancel");
      await refreshUser();
      toast.success(data.message);
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail) || "Erreur lors de l'annulation");
    } finally {
      setBusy(false);
    }
  };

  const resubscribe = async () => {
    setBusy(true);
    try {
      // Réactive le renouvellement automatique si l'abonnement Stripe est encore en période
      const { data } = await api.post("/subscription/reactivate");
      await refreshUser();
      toast.success(data.message);
      setBusy(false);
    } catch {
      // Abonnement non réactivable (expiré / sans Stripe) → nouveau paiement
      startCheckout();
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col">
      <Navbar />

      <main className="flex-1 mx-auto w-full max-w-5xl px-5 sm:px-8 py-12 sm:py-16">
        <p className="font-osd text-xs tracking-[0.25em] text-primary mb-3">[ MON COMPTE ]</p>
        <h1 className="font-display text-3xl sm:text-4xl font-extrabold tracking-tight" data-testid="dashboard-greeting">
          Salut, {user?.name || user?.email} 👋
        </h1>

        {checkingPayment && (
          <div
            className="mt-8 border border-[#d9ffd0]/40 bg-[#d9ffd0]/5 p-5 font-osd text-sm text-[#d9ffd0] animate-pulse"
            data-testid="payment-checking-banner"
          >
            VÉRIFICATION DU PAIEMENT EN COURS…
          </div>
        )}

        <div className="mt-10 grid md:grid-cols-2 gap-6">
          {/* ===== Abonnement ===== */}
          <section
            className={`bg-card border p-8 ${highlight ? "border-primary shadow-[0_0_30px_rgba(255,59,48,0.2)]" : "border-border"}`}
            data-testid="subscription-card"
          >
            <div className="flex items-center justify-between mb-6">
              <h2 className="font-display text-lg font-bold">Abonnement</h2>
              {isPro ? (
                <span
                  className={`font-osd text-[11px] tracking-[0.15em] px-3 py-1.5 ${
                    canceled ? "bg-secondary text-muted-foreground" : "bg-primary text-white"
                  }`}
                  data-testid="plan-badge"
                >
                  {canceled ? "PRO — ANNULÉ" : "PRO ✦"}
                </span>
              ) : (
                <span className="font-osd text-[11px] tracking-[0.15em] px-3 py-1.5 bg-secondary text-muted-foreground" data-testid="plan-badge">
                  GRATUIT
                </span>
              )}
            </div>

            {!isPro && (
              <>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  Tu utilises la version gratuite : tout le studio est dispo, avec un watermark BEATCUT sur l'aperçu.
                  Passe en PRO pour exporter tes vidéos sans watermark et récupérer tes .srt.
                </p>
                <p className="mt-5 font-display text-3xl font-extrabold">
                  9,99 € <span className="text-sm font-normal text-muted-foreground">/ mois — sans engagement</span>
                </p>
                <button
                  onClick={startCheckout}
                  disabled={busy}
                  data-testid="subscribe-pro-button"
                  className="mt-6 w-full inline-flex items-center justify-center gap-2 bg-primary text-white font-bold px-6 py-3.5 hover:bg-[#d32f2f] transition-all hover:-translate-y-0.5 shadow-[0_0_20px_rgba(255,59,48,0.35)] disabled:opacity-50"
                >
                  <Crown size={17} /> {busy ? "Redirection…" : "Passer en PRO"}
                </button>
                <p className="mt-3 text-xs text-muted-foreground text-center">
                  Paiement sécurisé par Stripe. Désabonnement en 1 clic.
                </p>
              </>
            )}

            {isPro && !canceled && (
              <>
                <div className="flex items-center gap-2.5 text-sm">
                  <BadgeCheck size={17} className="text-[#d9ffd0]" />
                  <span data-testid="subscription-status-text">Abonnement PRO actif</span>
                </div>
                <div className="mt-3 flex items-center gap-2.5 text-sm text-muted-foreground">
                  <CalendarClock size={17} />
                  <span data-testid="subscription-renewal-date">Accès jusqu'au {fmtDate(sub.current_period_end)}</span>
                </div>
                <p className="mt-5 text-sm text-muted-foreground leading-relaxed">
                  Export sans watermark, sous-titres .srt — tout est débloqué. Merci de soutenir BEATCUT ✦
                </p>
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <button
                      disabled={busy}
                      data-testid="unsubscribe-button"
                      className="mt-7 w-full border border-border text-muted-foreground px-6 py-3 text-sm hover:border-primary hover:text-primary transition-colors disabled:opacity-50"
                    >
                      Se désabonner
                    </button>
                  </AlertDialogTrigger>
                  <AlertDialogContent className="bg-card border-border">
                    <AlertDialogHeader>
                      <AlertDialogTitle className="font-display">Se désabonner de BEATCUT PRO ?</AlertDialogTitle>
                      <AlertDialogDescription>
                        Tu garderas l'accès PRO jusqu'au {fmtDate(sub.current_period_end)}. Ensuite, ton compte
                        repassera en gratuit (studio complet, aperçu avec watermark). Tu pourras te réabonner à tout moment.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel data-testid="cancel-unsubscribe-button">Garder mon abonnement</AlertDialogCancel>
                      <AlertDialogAction
                        onClick={cancelSubscription}
                        data-testid="confirm-unsubscribe-button"
                        className="bg-primary text-white hover:bg-[#d32f2f]"
                      >
                        Confirmer le désabonnement
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </>
            )}

            {isPro && canceled && (
              <>
                <div className="flex items-center gap-2.5 text-sm">
                  <CalendarClock size={17} className="text-primary" />
                  <span data-testid="subscription-status-text">
                    Abonnement annulé — accès PRO jusqu'au {fmtDate(sub.current_period_end)}
                  </span>
                </div>
                <p className="mt-5 text-sm text-muted-foreground leading-relaxed">
                  Après cette date, ton compte repassera automatiquement en gratuit. Tu peux te réabonner quand tu veux.
                </p>
                <button
                  onClick={resubscribe}
                  disabled={busy}
                  data-testid="resubscribe-button"
                  className="mt-7 w-full bg-primary text-white font-bold px-6 py-3.5 hover:bg-[#d32f2f] transition-colors disabled:opacity-50"
                >
                  {busy ? "…" : "Se réabonner — 9,99 €/mois"}
                </button>
              </>
            )}
          </section>

          {/* ===== Studio ===== */}
          <section className="bg-card border border-border p-8 flex flex-col" data-testid="studio-card">
            <div className="flex items-center justify-between mb-6">
              <h2 className="font-display text-lg font-bold">Le studio</h2>
              <span className="font-osd text-[11px] tracking-[0.15em] text-[#d9ffd0] flex items-center gap-2">
                <span className="rec-dot" /> READY
              </span>
            </div>
            <p className="text-sm text-muted-foreground leading-relaxed flex-1">
              Dépose ton track, ajoute tes clips, lance la détection IA des paroles et exporte ta vidéo
              calée sur le beat. Tout se passe dans ton navigateur — rien n'est envoyé sur nos serveurs.
            </p>
            <Link
              to="/studio"
              data-testid="open-studio-button"
              className="mt-7 inline-flex items-center justify-center gap-2 bg-foreground text-background font-bold px-6 py-3.5 hover:opacity-90 transition-all hover:-translate-y-0.5"
            >
              <Clapperboard size={17} /> Ouvrir le studio <ArrowRight size={15} />
            </Link>
          </section>
        </div>

        {/* ===== Infos compte ===== */}
        <section className="mt-6 bg-card border border-border p-8" data-testid="account-info-card">
          <h2 className="font-display text-lg font-bold mb-5">Informations</h2>
          <div className="grid sm:grid-cols-3 gap-5 text-sm">
            <div>
              <p className="font-osd text-[11px] tracking-[0.15em] text-muted-foreground mb-1.5">EMAIL</p>
              <p data-testid="account-email">{user?.email}</p>
            </div>
            <div>
              <p className="font-osd text-[11px] tracking-[0.15em] text-muted-foreground mb-1.5">NOM</p>
              <p data-testid="account-name">{user?.name || "—"}</p>
            </div>
            <div>
              <p className="font-osd text-[11px] tracking-[0.15em] text-muted-foreground mb-1.5">CONNEXION</p>
              <p data-testid="account-provider">{user?.auth_provider === "google" ? "Google" : "Email + mot de passe"}</p>
            </div>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
}
