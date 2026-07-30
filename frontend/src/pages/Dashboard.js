import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { Clapperboard, Crown, BadgeCheck, CalendarClock, ArrowRight } from "lucide-react";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import { useAuth } from "@/context/AuthContext";
import api, { formatApiErrorDetail } from "@/lib/api";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

const fmtDate = (iso) =>
  iso ? new Date(iso).toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" }) : "";

const CANCEL_REASONS = [
  ["too_expensive", "💸 Trop cher pour moi"],
  ["not_enough_use", "🕒 Je ne l'utilise pas assez"],
  ["missing_features", "🧩 Il manque des fonctionnalités"],
  ["technical_issues", "🐞 Problèmes techniques / bugs"],
  ["promo_done", "🎤 Ma promo est terminée"],
  ["other", "🤷 Autre raison"],
];

export default function Dashboard() {
  const { user, refreshUser } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const sessionId = params.get("session_id");
  const highlight = params.get("upgrade") === "1";
  const [checkingPayment, setCheckingPayment] = useState(!!sessionId);
  const [busy, setBusy] = useState(false);
  const pollRef = useRef(false);

  // Nouveau compte : onboarding (5 écrans) dans le studio avant tout
  useEffect(() => {
    if (!sessionId && user && user.onboarding_done === false) navigate("/studio", { replace: true });
  }, [user, navigate, sessionId]);

  const sub = user?.subscription || {};
  const isPro = !!user?.is_pro;
  const isVip = sub.status === "vip";
  const canceled = !!sub.cancel_at_period_end;
  const tier = sub.tier || (isPro ? "pro" : "free");
  const isBasic = tier === "basic";
  const isEssentiel = tier === "essentiel";
  const isStudio = tier === "studio";
  const isTrial = !!sub.trial;
  const hasQuota = isBasic || isEssentiel || isTrial;
  const [quota, setQuota] = useState(null);
  const LEGACY_EQUIV = { pro_monthly: "monthly", pro_yearly: "yearly", essentiel: "basic" };

  useEffect(() => {
    if (!hasQuota) return;
    api.get("/export/quota").then(({ data }) => setQuota(data)).catch(() => {});
  }, [hasQuota]);

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
          toast.success("Paiement confirmé — ton abonnement est actif ! 🎉");
          navigate("/dashboard", { replace: true });
          return;
        }
        if (data.payment_status === "trial_refused") {
          setCheckingPayment(false);
          toast.error("Essai déjà utilisé avec cette carte — choisis un abonnement sans essai.");
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

  const startCheckout = async (plan = "pro_monthly") => {
    setBusy(true);
    try {
      const payload = { origin_url: window.location.origin, plan };
      const covered = affiliate?.plans?.includes(plan) || affiliate?.plans?.includes(LEGACY_EQUIV[plan]);
      if (affiliate?.code && covered) payload.promo_code = affiliate.code;
      const { data } = await api.post("/payments/checkout", payload);
      window.location.href = data.url;
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail) || "Erreur lors de la création du paiement");
      setBusy(false);
    }
  };

  const [promoCode, setPromoCode] = useState("");
  const [promoBusy, setPromoBusy] = useState(false);
  const [refInfo, setRefInfo] = useState(null);
  const [affiliate, setAffiliate] = useState(null);
  const fmtEUR = (c) => (c / 100).toFixed(2).replace(".", ",");
  const affPrice = (plan) => (affiliate && affiliate.prices?.[plan]) || null;
  const promoBadge = (plan) =>
    affPrice(plan) ? (
      <span
        className="absolute -top-2.5 left-2 bg-[#d9ffd0] text-background font-osd text-[9px] tracking-wider px-2 py-0.5"
        data-testid={`promo-badge-${plan}`}
      >
        🎁 {affiliate.code}
      </span>
    ) : null;

  useEffect(() => {
    // code saisi manuellement (persistant) prioritaire sur un code venu d'un lien (session en cours)
    const saved = localStorage.getItem("bc_affiliate_manual") || sessionStorage.getItem("bc_affiliate_link");
    if (!saved) return;
    api.get(`/affiliate/check/${encodeURIComponent(saved)}`)
      .then(({ data }) => setAffiliate(data))
      .catch(() => {
        localStorage.removeItem("bc_affiliate_manual");
        sessionStorage.removeItem("bc_affiliate_link");
      });
  }, []);

  useEffect(() => {
    if (!user) return;
    api.get("/promo/me").then(({ data }) => setRefInfo(data)).catch(() => {});
  }, [user]);

  const applyPromo = async (e) => {
    e.preventDefault();
    if (!promoCode.trim()) return;
    setPromoBusy(true);
    try {
      const { data } = await api.post("/promo/apply", { code: promoCode.trim() });
      await refreshUser();
      toast.success(data.message);
      setPromoCode("");
    } catch (err) {
      // pas un code « jours offerts » ? → peut-être un code AFFILIÉ (remise à vie sur l'abonnement)
      try {
        const { data } = await api.get(`/affiliate/check/${encodeURIComponent(promoCode.trim())}`);
        localStorage.setItem("bc_affiliate_manual", data.code);
        setAffiliate(data);
        toast.success(`Code ${data.code} activé — la réduction s'appliquera automatiquement au paiement, à vie ✓`);
        setPromoCode("");
      } catch {
        toast.error(formatApiErrorDetail(err.response?.data?.detail) || "Code invalide");
      }
    } finally {
      setPromoBusy(false);
    }
  };

  const copyRef = async () => {
    if (!refInfo?.ref_code) return;
    const link = `${window.location.origin}/register?ref=${refInfo.ref_code}`;
    try {
      await navigator.clipboard.writeText(link);
      toast.success("Lien de parrainage copié !");
    } catch {
      toast.error("Copie impossible — sélectionne le lien manuellement");
    }
  };

  const [wmBusy, setWmBusy] = useState(false);
  const [cancelOpen, setCancelOpen] = useState(false);
  const [cancelStep, setCancelStep] = useState("reason");
  const [cancelReason, setCancelReason] = useState("");
  const [cancelComment, setCancelComment] = useState("");
  const [offerAvailable, setOfferAvailable] = useState(false);

  const openCancelFlow = () => {
    setCancelReason("");
    setCancelComment("");
    setCancelStep("reason");
    setCancelOpen(true);
  };

  const submitCancelFeedback = async () => {
    if (!cancelReason) return;
    setBusy(true);
    try {
      const { data } = await api.post("/subscription/cancel-feedback", {
        reason: cancelReason,
        comment: cancelComment,
      });
      setOfferAvailable(!!data.offer_available);
      setCancelStep("offer");
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail) || "Erreur — réessaie");
    } finally {
      setBusy(false);
    }
  };

  const acceptRetention = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/subscription/retention-accept");
      toast.success(data.message);
      setCancelOpen(false);
      await refreshUser();
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail) || "Erreur — réessaie");
    } finally {
      setBusy(false);
    }
  };

  const confirmCancelNow = async () => {
    setCancelOpen(false);
    await cancelSubscription();
  };

  const [activateOpen, setActivateOpen] = useState(false);
  const activateNow = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/payments/activate-now");
      toast.success(data.message);
      setActivateOpen(false);
      await refreshUser();
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail) || "Activation impossible — réessaie");
    } finally {
      setBusy(false);
    }
  };

  const uploadWatermark = async (file) => {
    if (!file) return;
    setWmBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      await api.post("/studio/watermark", fd);
      await refreshUser();
      toast.success("Logo enregistré — il sera incrusté sur tes prochains exports ✓");
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail) || "Envoi impossible");
    } finally {
      setWmBusy(false);
    }
  };
  const removeWatermark = async () => {
    setWmBusy(true);
    try {
      await api.delete("/studio/watermark");
      await refreshUser();
      toast.success("Logo retiré");
    } finally {
      setWmBusy(false);
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
                  isVip ? "bg-[#d9ffd0] text-background" : canceled ? "bg-secondary text-muted-foreground" : isBasic ? "bg-[#8f9bff] text-background" : "bg-primary text-white"
                }`}
                data-testid="plan-badge"
              >
                {isVip ? "VIP ✦" : isTrial ? "ESSAI PRO — 7 JOURS" : canceled ? (isBasic ? "BASIC — ANNULÉ" : isEssentiel ? "ESSENTIEL — ANNULÉ" : "PRO — ANNULÉ") : isBasic ? "BASIC" : isEssentiel ? "ESSENTIEL" : isStudio ? "STUDIO ✦" : "PRO ✦"}
              </span>
            ) : (
                <span className="font-osd text-[11px] tracking-[0.15em] px-3 py-1.5 bg-secondary text-muted-foreground" data-testid="plan-badge">
                  SANS ABONNEMENT
                </span>
              )}
            </div>

            {isVip && (
              <div data-testid="vip-section">
                <div className="flex items-center gap-2.5 text-sm">
                  <BadgeCheck size={17} className="text-[#d9ffd0]" />
                  <span data-testid="subscription-status-text">Compte VIP — accès PRO illimité ✦</span>
                </div>
                <p className="mt-5 text-sm text-muted-foreground leading-relaxed">
                  Export sans watermark, sous-titres .srt et extraction d'acapella — tout est débloqué à vie,
                  sans abonnement ni paiement. Profite bien ✦
                </p>
              </div>
            )}

            {!isPro && (
              <>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  Ton studio est prêt : montage complet, aperçu et sauvegarde inclus. Choisis ton plan pour
                  exporter tes vidéos — <b className="text-foreground">7 jours d'essai offerts</b> sur le plan Pro,
                  annulable en 2 clics avant le débit.
                </p>
                <div className="grid gap-3 mt-6">
                  <button
                    onClick={() => startCheckout("pro_monthly")}
                    disabled={busy}
                    data-testid="subscribe-pro-button"
                    className="relative inline-flex items-center justify-between gap-2 bg-primary text-white font-bold px-5 py-3.5 hover:bg-[#d32f2f] transition-all hover:-translate-y-0.5 shadow-[0_0_20px_rgba(255,59,48,0.35)] disabled:opacity-50"
                  >
                    <span className="absolute -top-2.5 right-2 bg-white text-primary font-osd text-[9px] tracking-wider px-2 py-0.5">
                      7 JOURS OFFERTS
                    </span>
                    {promoBadge("pro_monthly")}
                    <span className="inline-flex items-center gap-2"><Crown size={16} /> PRO — essai 7 jours</span>
                    <span className="font-display" data-testid="price-pro-monthly">
                      {affPrice("pro_monthly") ? (
                        <><s className="opacity-60 mr-1.5">19,99 €</s>{fmtEUR(affPrice("pro_monthly").after_cents)} €/mois</>
                      ) : "19,99 €/mois"}
                    </span>
                  </button>
                  <p className="text-[11px] text-muted-foreground text-center -mt-1">
                    Exports illimités + séries de vidéos · puis 19,99 €/mois · annulable pendant l'essai
                  </p>
                  <button
                    onClick={() => startCheckout("essentiel")}
                    disabled={busy}
                    data-testid="subscribe-essentiel-button"
                    className="relative inline-flex items-center justify-between gap-2 border border-[#8f9bff]/60 bg-[#8f9bff]/10 text-foreground font-bold px-5 py-3.5 hover:bg-[#8f9bff]/20 transition-all hover:-translate-y-0.5 disabled:opacity-50"
                  >
                    {promoBadge("essentiel")}
                    <span>ESSENTIEL — 15 exports/mois</span>
                    <span className="font-display" data-testid="price-essentiel">
                      {affPrice("essentiel") ? (
                        <><s className="opacity-50 mr-1.5">9,99 €</s>{fmtEUR(affPrice("essentiel").after_cents)} €/mois</>
                      ) : "9,99 €/mois"}
                    </span>
                  </button>
                  <button
                    onClick={() => startCheckout("pro_yearly")}
                    disabled={busy}
                    data-testid="subscribe-pro-yearly-button"
                    className="relative inline-flex items-center justify-between gap-2 border border-[#ffd97a]/50 bg-[#ffd97a]/5 text-foreground font-bold px-5 py-3.5 hover:bg-[#ffd97a]/10 transition-all hover:-translate-y-0.5 disabled:opacity-50"
                  >
                    <span className="absolute -top-2.5 right-2 bg-[#ffd97a] text-background font-osd text-[9px] tracking-wider px-2 py-0.5">
                      MEILLEURE AFFAIRE · −38 %
                    </span>
                    {promoBadge("pro_yearly")}
                    <span>PRO Annuel — 12,42 €/mois</span>
                    <span className="font-display" data-testid="price-pro-yearly">
                      {affPrice("pro_yearly") ? (
                        <><s className="opacity-50 mr-1.5">149 €</s>{fmtEUR(affPrice("pro_yearly").after_cents)} €/an</>
                      ) : "149 €/an"}
                    </span>
                  </button>
                  <a
                    href="mailto:jules.beatcut@gmail.com?subject=D%C3%A9mo%20BeatCut%20Studio"
                    data-testid="subscribe-studio-button"
                    className="relative inline-flex items-center justify-between gap-2 border border-border text-foreground font-bold px-5 py-3.5 hover:border-foreground transition-all hover:-translate-y-0.5"
                  >
                    <span>STUDIO — 5 profils artistes</span>
                    <span className="font-display">499 €/an · Planifier une démo</span>
                  </a>
                </div>
                <p className="mt-3 text-xs text-muted-foreground text-center">
                  Sans engagement (mensuel) · 🎁 7 jours offerts avec rappel par email avant le débit · Paiement sécurisé Stripe.
                </p>
              </>
            )}

            {isPro && !canceled && !isVip && (
              <>
                <div className="flex items-center gap-2.5 text-sm">
                  <BadgeCheck size={17} className="text-[#d9ffd0]" />
                  <span data-testid="subscription-status-text">
                    {isTrial ? "Essai Pro en cours — accès complet" : isBasic ? "Abonnement BASIC actif" : isEssentiel ? "Abonnement ESSENTIEL actif" : isStudio ? "Abonnement STUDIO actif" : "Abonnement PRO actif"}
                  </span>
                </div>
                <div className="mt-3 flex items-center gap-2.5 text-sm text-muted-foreground">
                  <CalendarClock size={17} />
                  <span data-testid="subscription-renewal-date">
                    {isTrial
                      ? `Ton abonnement Pro (19,99 €/mois) démarre le ${fmtDate(sub.current_period_end)} — annulable en 2 clics avant le débit`
                      : `Accès jusqu'au ${fmtDate(sub.current_period_end)}`}
                  </span>
                </div>
                {isTrial && (
                  <div className="mt-4 border border-primary/40 bg-primary/5 px-4 py-3 font-osd text-xs tracking-wider text-primary" data-testid="trial-day-banner">
                    ESSAI PRO — J{Math.min(7, Math.max(1, 7 - Math.max(0, Math.ceil((new Date(sub.current_period_end) - Date.now()) / 86400000)) + 1))}/7
                  </div>
                )}
                {isTrial && (
                  <>
                    <button
                      onClick={() => setActivateOpen(true)}
                      disabled={busy}
                      data-testid="activate-now-button"
                      className="relative mt-4 w-full inline-flex items-center justify-center gap-2 bg-primary text-white font-bold px-6 py-3.5 hover:bg-[#d32f2f] transition-all hover:-translate-y-0.5 shadow-[0_0_20px_rgba(255,59,48,0.35)] disabled:opacity-50"
                    >
                      <Crown size={16} /> Déjà convaincu ? Passer en illimité maintenant
                    </button>
                    <p className="mt-2 text-xs text-muted-foreground text-center">
                      Ton abonnement Pro démarre tout de suite — exports illimités débloqués immédiatement.
                    </p>
                  </>
                )}
                {hasQuota && quota && quota.quota != null && (
                  <div className="mt-5" data-testid="quota-section">
                    <div className="flex items-center justify-between text-sm mb-2">
                      <span className="text-muted-foreground">
                        {isTrial ? "Exports pendant l'essai" : "Vidéos exportées ce mois-ci"}
                      </span>
                      <span className="font-osd text-[#8f9bff]" data-testid="quota-count">
                        {quota.used} / {quota.quota}
                      </span>
                    </div>
                    <div className="h-2 bg-secondary overflow-hidden">
                      <div
                        className="h-full bg-[#8f9bff] transition-all"
                        style={{ width: `${Math.min(100, (quota.used / quota.quota) * 100)}%` }}
                      />
                    </div>
                  </div>
                )}
                {(isBasic || isEssentiel) && (
                  <>
                    <p className="mt-5 text-sm text-muted-foreground leading-relaxed">
                      {isBasic
                        ? "Export sans watermark et .srt inclus — 10 vidéos par mois. Passe en PRO pour exporter en illimité et débloquer les séries de vidéos."
                        : "15 exports par mois, tous les styles et effets. Passe en PRO pour exporter en illimité et débloquer les séries de vidéos."}
                    </p>
                    <button
                      onClick={() => startCheckout("pro_monthly")}
                      disabled={busy}
                      data-testid="upgrade-to-pro-button"
                      className="relative mt-6 w-full inline-flex items-center justify-center gap-2 bg-primary text-white font-bold px-6 py-3.5 hover:bg-[#d32f2f] transition-all hover:-translate-y-0.5 shadow-[0_0_20px_rgba(255,59,48,0.35)] disabled:opacity-50"
                    >
                      {promoBadge("pro_monthly")}
                      <Crown size={16} /> Passer en PRO —{" "}
                      {affPrice("pro_monthly") ? (
                        <span data-testid="price-upgrade-monthly"><s className="opacity-60 mr-1">19,99 €</s>{fmtEUR(affPrice("pro_monthly").after_cents)} €/mois</span>
                      ) : "19,99 €/mois"}
                    </button>
                    <p className="mt-2 text-xs text-muted-foreground text-center">
                      Ton abonnement actuel sera automatiquement remplacé.
                    </p>
                  </>
                )}
                {!isBasic && !isEssentiel && !isTrial && (
                  <p className="mt-5 text-sm text-muted-foreground leading-relaxed">
                    Exports illimités, séries de vidéos, tous les styles — tout est débloqué. Merci de soutenir BEATCUT ✦
                  </p>
                )}
                <button
                  onClick={openCancelFlow}
                  disabled={busy}
                  data-testid="unsubscribe-button"
                  className="mt-7 w-full border border-border text-muted-foreground px-6 py-3 text-sm hover:border-primary hover:text-primary transition-colors disabled:opacity-50"
                >
                  {isTrial ? "Annuler mon essai" : "Se désabonner"}
                </button>
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
                  Après cette date, ton compte repassera sans abonnement (montage et sauvegarde conservés, export
                  verrouillé). Tu peux te réabonner quand tu veux.
                </p>
                <button
                  onClick={resubscribe}
                  disabled={busy}
                  data-testid="resubscribe-button"
                  className="mt-7 w-full bg-primary text-white font-bold px-6 py-3.5 hover:bg-[#d32f2f] transition-colors disabled:opacity-50"
                >
                  {busy ? "…" : "Se réabonner"}
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

        {isStudio && (
          <section className="mt-6 bg-card border border-border p-8" data-testid="studio-watermark-card">
            <h2 className="font-display text-lg font-bold mb-3">Watermark personnalisé ✦ Studio</h2>
            <p className="text-sm text-muted-foreground leading-relaxed">
              Ajoute le logo de ta structure (PNG, fond transparent conseillé) : il sera incrusté en bas à droite
              de chaque vidéo exportée depuis ce compte.
            </p>
            <div className="mt-5 flex items-center gap-3 flex-wrap">
              <label className="cursor-pointer bg-foreground text-background font-bold px-5 py-2.5 text-sm hover:opacity-90 transition-opacity">
                {wmBusy ? "…" : user?.has_watermark ? "Remplacer le logo" : "Ajouter mon logo (PNG)"}
                <input
                  type="file"
                  accept="image/png"
                  className="hidden"
                  data-testid="watermark-upload-input"
                  onChange={(e) => uploadWatermark(e.target.files?.[0])}
                />
              </label>
              {user?.has_watermark && (
                <>
                  <img src="/api/studio/watermark" alt="logo" className="h-10 border border-border bg-background p-1" data-testid="watermark-preview" />
                  <button
                    onClick={removeWatermark}
                    disabled={wmBusy}
                    data-testid="watermark-delete-button"
                    className="border border-border text-muted-foreground px-4 py-2.5 text-sm hover:border-primary hover:text-primary transition-colors"
                  >
                    Retirer
                  </button>
                </>
              )}
            </div>
          </section>
        )}

        {/* ===== Parrainage + Promo ===== */}
        <section className="mt-6 grid md:grid-cols-2 gap-6">
          <div className="bg-card border border-border p-8 min-w-0" data-testid="referral-card">
            <h2 className="font-display text-lg font-bold mb-3">Parrainage ✦</h2>
            <p className="text-sm text-muted-foreground leading-relaxed">
              Invite un ami : <b>+1 mois offert</b> pour lui ET pour toi dès qu'il prend un abonnement payant.
            </p>
            {refInfo?.ref_code && (
              <>
                <div className="mt-5 bg-background border border-border px-4 py-3 flex items-center gap-3 overflow-hidden">
                  <code className="font-osd text-xs text-[#d9ffd0] truncate flex-1" data-testid="referral-link">
                    {window.location.origin}/register?ref={refInfo.ref_code}
                  </code>
                  <button
                    onClick={copyRef}
                    data-testid="copy-referral-button"
                    className="font-osd text-[11px] tracking-wider text-foreground border border-border px-3 py-1.5 hover:border-foreground transition-colors"
                  >
                    COPIER
                  </button>
                </div>
                <p className="mt-3 text-xs text-muted-foreground" data-testid="referral-count">
                  {refInfo.referral_count > 0
                    ? `${refInfo.referral_count} ami${refInfo.referral_count > 1 ? "s" : ""} parrainé${refInfo.referral_count > 1 ? "s" : ""} ✦`
                    : "Aucun parrainage pour l'instant."}
                </p>
              </>
            )}
          </div>

          <div className="bg-card border border-border p-8 min-w-0" data-testid="promo-card">
            <h2 className="font-display text-lg font-bold mb-3">Code promo</h2>
            <p className="text-sm text-muted-foreground leading-relaxed">
              Tu as déniché un code promo ? Rentre-le ici.
            </p>
            <form onSubmit={applyPromo} className="mt-5 flex gap-3">
              <input
                value={promoCode}
                onChange={(e) => setPromoCode(e.target.value.toUpperCase())}
                placeholder="EX: LAUNCH30"
                data-testid="promo-input"
                className="flex-1 bg-background border border-border px-4 py-2.5 text-sm font-osd tracking-wider focus:border-[#d9ffd0] focus:outline-none transition-colors"
              />
              <button
                type="submit"
                disabled={promoBusy || !promoCode.trim()}
                data-testid="promo-submit"
                className="bg-primary text-white font-bold px-5 py-2.5 hover:bg-[#d32f2f] transition-colors disabled:opacity-50"
              >
                {promoBusy ? "…" : "Activer"}
              </button>
            </form>
          </div>
        </section>

        {user?.role === "admin" && (
          <p className="mt-8 text-xs text-muted-foreground">
            <Link to="/admin" data-testid="admin-link" className="underline underline-offset-4">
              → Tableau de bord admin
            </Link>
          </p>
        )}
      </main>

      <Footer />

      <Dialog open={cancelOpen} onOpenChange={setCancelOpen}>
        <DialogContent className="bg-card border-border sm:max-w-md" data-testid="cancel-flow-modal">
          {cancelStep === "reason" ? (
            <>
              <DialogHeader>
                <DialogTitle className="font-display">Avant de partir… dis-nous pourquoi 🙏</DialogTitle>
                <DialogDescription>30 secondes — ça nous aide vraiment à améliorer BEATCUT.</DialogDescription>
              </DialogHeader>
              <div className="grid gap-2 mt-1">
                {CANCEL_REASONS.map(([val, label]) => (
                  <button
                    key={val}
                    onClick={() => setCancelReason(val)}
                    data-testid={`cancel-reason-${val}`}
                    className={`text-left text-sm px-4 py-2.5 border transition-colors ${
                      cancelReason === val
                        ? "border-primary bg-primary/10 text-foreground"
                        : "border-border text-muted-foreground hover:border-foreground"
                    }`}
                  >
                    {label}
                  </button>
                ))}
                <textarea
                  value={cancelComment}
                  onChange={(e) => setCancelComment(e.target.value)}
                  maxLength={500}
                  placeholder="Un détail à ajouter ? (facultatif)"
                  data-testid="cancel-comment-input"
                  className="mt-1 bg-background border border-border px-3 py-2 text-sm min-h-[70px] resize-none"
                />
              </div>
              <div className="flex justify-between items-center mt-2">
                <button
                  onClick={() => setCancelOpen(false)}
                  data-testid="cancel-flow-keep-button"
                  className="text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                  {isTrial ? "Garder mon essai" : "Garder mon abonnement"}
                </button>
                <button
                  onClick={submitCancelFeedback}
                  disabled={!cancelReason || busy}
                  data-testid="cancel-feedback-continue-button"
                  className="bg-primary text-white font-bold px-5 py-2.5 text-sm hover:bg-[#d32f2f] transition-colors disabled:opacity-40"
                >
                  {busy ? "…" : "Continuer"}
                </button>
              </div>
            </>
          ) : (
            <>
              <DialogHeader>
                <DialogTitle className="font-display">
                  {offerAvailable ? "Attends — on t'offre −50 % ✦" : (isTrial ? "Annuler ton essai Pro ?" : "Confirmer l'annulation ?")}
                </DialogTitle>
                <DialogDescription>
                  {offerAvailable
                    ? `−50 % sur ta prochaine facture, appliqué automatiquement. Tu gardes tout : ${isTrial ? "ton essai puis ton accès Pro complet" : "exports, séries, styles"} — et tu restes libre d'annuler quand tu veux.`
                    : isTrial
                      ? "Ton essai sera annulé immédiatement : rien ne sera débité. Ton montage et tes morceaux restent sauvegardés."
                      : `Tu garderas l'accès jusqu'au ${fmtDate(sub.current_period_end)}. Ensuite, l'export sera verrouillé (montage et sauvegarde conservés).`}
                </DialogDescription>
              </DialogHeader>
              <div className="grid gap-2 mt-2">
                {offerAvailable && (
                  <button
                    onClick={acceptRetention}
                    disabled={busy}
                    data-testid="retention-accept-button"
                    className="bg-primary text-white font-bold px-5 py-3 hover:bg-[#d32f2f] transition-colors disabled:opacity-50 shadow-[0_0_20px_rgba(255,59,48,0.35)]"
                  >
                    {busy ? "…" : "✦ J'accepte −50 % et je reste"}
                  </button>
                )}
                <button
                  onClick={confirmCancelNow}
                  disabled={busy}
                  data-testid="confirm-unsubscribe-button"
                  className="border border-border text-muted-foreground px-5 py-3 text-sm hover:border-primary hover:text-primary transition-colors disabled:opacity-50"
                >
                  {isTrial ? "Annuler mon essai quand même (aucun débit)" : "Annuler quand même"}
                </button>
                {!offerAvailable && (
                  <button
                    onClick={() => setCancelOpen(false)}
                    data-testid="cancel-unsubscribe-button"
                    className="text-sm text-muted-foreground hover:text-foreground transition-colors py-1"
                  >
                    {isTrial ? "Garder mon essai" : "Garder mon abonnement"}
                  </button>
                )}
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={activateOpen} onOpenChange={setActivateOpen}>
        <DialogContent className="bg-card border-border sm:max-w-md" data-testid="activate-now-modal">
          <DialogHeader>
            <DialogTitle className="font-display">Activer ton abonnement Pro maintenant ?</DialogTitle>
            <DialogDescription>
              Ton essai se termine immédiatement : <b className="text-foreground">19,99 €</b> sont débités aujourd'hui
              sur ta carte, et tu débloques les <b className="text-foreground">exports illimités</b> tout de suite.
              Ton prochain débit aura lieu dans un mois.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-2 mt-2">
            <button
              onClick={activateNow}
              disabled={busy}
              data-testid="confirm-activate-now-button"
              className="bg-primary text-white font-bold px-5 py-3 hover:bg-[#d32f2f] transition-colors disabled:opacity-50 shadow-[0_0_20px_rgba(255,59,48,0.35)]"
            >
              {busy ? "…" : "⚡ Activer maintenant — 19,99 €"}
            </button>
            <button
              onClick={() => setActivateOpen(false)}
              data-testid="cancel-activate-now-button"
              className="text-sm text-muted-foreground hover:text-foreground transition-colors py-1"
            >
              Continuer mon essai gratuit
            </button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
