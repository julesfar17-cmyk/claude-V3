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
  const isVip = sub.status === "vip";
  const canceled = !!sub.cancel_at_period_end;
  const tier = sub.tier || (isPro ? "pro" : "free");
  const isBasic = tier === "basic";
  const [quota, setQuota] = useState(null);

  useEffect(() => {
    if (!isBasic) return;
    api.get("/export/quota").then(({ data }) => setQuota(data)).catch(() => {});
  }, [isBasic]);

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

  const startCheckout = async (plan = "monthly") => {
    setBusy(true);
    try {
      const payload = { origin_url: window.location.origin, plan };
      if (affiliate?.code && affiliate.plans?.includes(plan)) payload.promo_code = affiliate.code;
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

  useEffect(() => {
    // code affilié mémorisé (lien ?promo=CODE) : re-validé au chargement
    const saved = localStorage.getItem("bc_affiliate");
    if (!saved) return;
    api.get(`/affiliate/check/${encodeURIComponent(saved)}`)
      .then(({ data }) => setAffiliate(data))
      .catch(() => localStorage.removeItem("bc_affiliate"));
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
        localStorage.setItem("bc_affiliate", data.code);
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
                {isVip ? "VIP ✦" : canceled ? (isBasic ? "BASIC — ANNULÉ" : "PRO — ANNULÉ") : isBasic ? "BASIC" : "PRO ✦"}
              </span>
            ) : (
                <span className="font-osd text-[11px] tracking-[0.15em] px-3 py-1.5 bg-secondary text-muted-foreground" data-testid="plan-badge">
                  GRATUIT
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
                {affiliate && (
                  <div className="mb-4 border border-primary/50 bg-primary/10 px-4 py-3 text-sm" data-testid="affiliate-active-banner">
                    🎁 Code <b className="font-osd">{affiliate.code}</b> actif —{" "}
                    {Object.values(affiliate.prices || {}).map((p, i) => (
                      <span key={p.label}>{i > 0 && " · "}{p.label} : <s className="text-muted-foreground">{(p.base_cents / 100).toFixed(2).replace(".", ",")} €</s> <b>{(p.after_cents / 100).toFixed(2).replace(".", ",")} €</b></span>
                    ))}{" "}
                    <span className="text-muted-foreground">à vie, appliqué automatiquement au paiement</span>
                  </div>
                )}
                <p className="text-sm text-muted-foreground leading-relaxed">
                  Tu utilises la version gratuite : tout le studio est dispo, avec un watermark BEATCUT sur l'aperçu.
                  Choisis ton plan pour exporter tes vidéos sans watermark.
                </p>
                <div className="grid gap-3 mt-6">
                  <button
                    onClick={() => startCheckout("basic")}
                    disabled={busy}
                    data-testid="subscribe-basic-button"
                    className="inline-flex items-center justify-between gap-2 border border-[#8f9bff]/60 bg-[#8f9bff]/10 text-foreground font-bold px-5 py-3.5 hover:bg-[#8f9bff]/20 transition-all hover:-translate-y-0.5 disabled:opacity-50"
                  >
                    <span>BASIC — 10 vidéos/mois</span>
                    <span className="font-display">6,99 €/mois</span>
                  </button>
                  <button
                    onClick={() => startCheckout("monthly")}
                    disabled={busy}
                    data-testid="subscribe-pro-button"
                    className="relative inline-flex items-center justify-between gap-2 bg-primary text-white font-bold px-5 py-3.5 hover:bg-[#d32f2f] transition-all hover:-translate-y-0.5 shadow-[0_0_20px_rgba(255,59,48,0.35)] disabled:opacity-50"
                  >
                    <span className="absolute -top-2.5 right-2 bg-white text-primary font-osd text-[9px] tracking-wider px-2 py-0.5">
                      RECOMMANDÉ
                    </span>
                    <span className="inline-flex items-center gap-2"><Crown size={16} /> PRO — illimité + acapella</span>
                    <span className="font-display">12,99 €/mois</span>
                  </button>
                  <button
                    onClick={() => startCheckout("yearly")}
                    disabled={busy}
                    data-testid="subscribe-pro-yearly-button"
                    className="relative inline-flex items-center justify-between gap-2 border border-[#d9ffd0]/50 bg-[#d9ffd0]/5 text-foreground font-bold px-5 py-3.5 hover:bg-[#d9ffd0]/10 transition-all hover:-translate-y-0.5 disabled:opacity-50"
                  >
                    <span className="absolute -top-2.5 right-2 bg-[#d9ffd0] text-background font-osd text-[9px] tracking-wider px-2 py-0.5">
                      2 MOIS OFFERTS
                    </span>
                    <span>PRO annuel</span>
                    <span className="font-display">99 €/an</span>
                  </button>
                </div>
                <p className="mt-3 text-xs text-muted-foreground text-center">
                  Paiement sécurisé par Stripe. Désabonnement en 1 clic.
                </p>
              </>
            )}

            {isPro && !canceled && !isVip && (
              <>
                <div className="flex items-center gap-2.5 text-sm">
                  <BadgeCheck size={17} className="text-[#d9ffd0]" />
                  <span data-testid="subscription-status-text">
                    {isBasic ? "Abonnement BASIC actif" : "Abonnement PRO actif"}
                  </span>
                </div>
                <div className="mt-3 flex items-center gap-2.5 text-sm text-muted-foreground">
                  <CalendarClock size={17} />
                  <span data-testid="subscription-renewal-date">Accès jusqu'au {fmtDate(sub.current_period_end)}</span>
                </div>
                {isBasic ? (
                  <>
                    {quota && (
                      <div className="mt-5" data-testid="basic-quota-section">
                        <div className="flex items-center justify-between text-sm mb-2">
                          <span className="text-muted-foreground">Vidéos exportées ce mois-ci</span>
                          <span className="font-osd text-[#8f9bff]" data-testid="basic-quota-count">
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
                    <p className="mt-5 text-sm text-muted-foreground leading-relaxed">
                      Export sans watermark et .srt inclus — 10 vidéos par mois. Passe en PRO pour exporter en
                      illimité et débloquer l'extraction d'acapella (IA).
                    </p>
                    <button
                      onClick={() => startCheckout("monthly")}
                      disabled={busy}
                      data-testid="upgrade-to-pro-button"
                      className="mt-6 w-full inline-flex items-center justify-center gap-2 bg-primary text-white font-bold px-6 py-3.5 hover:bg-[#d32f2f] transition-all hover:-translate-y-0.5 shadow-[0_0_20px_rgba(255,59,48,0.35)] disabled:opacity-50"
                    >
                      <Crown size={16} /> Passer en PRO — 12,99 €/mois
                    </button>
                    <p className="mt-2 text-xs text-muted-foreground text-center">
                      Ton abonnement BASIC sera automatiquement remplacé.
                    </p>
                  </>
                ) : (
                  <p className="mt-5 text-sm text-muted-foreground leading-relaxed">
                    Export sans watermark, sous-titres .srt, acapella — tout est débloqué. Merci de soutenir BEATCUT ✦
                  </p>
                )}
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
                      <AlertDialogTitle className="font-display">
                        Se désabonner de BEATCUT {isBasic ? "BASIC" : "PRO"} ?
                      </AlertDialogTitle>
                      <AlertDialogDescription>
                        Tu garderas l'accès {isBasic ? "BASIC" : "PRO"} jusqu'au {fmtDate(sub.current_period_end)}. Ensuite, ton compte
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
                  {busy ? "…" : "Se réabonner — 12,99 €/mois"}
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

        {/* ===== Parrainage + Promo ===== */}
        <section className="mt-6 grid md:grid-cols-2 gap-6">
          <div className="bg-card border border-border p-8" data-testid="referral-card">
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

          <div className="bg-card border border-border p-8" data-testid="promo-card">
            <h2 className="font-display text-lg font-bold mb-3">Code promo</h2>
            <p className="text-sm text-muted-foreground leading-relaxed">
              Tu as un code (lancement, créateur, événement) ? Active-le pour des jours offerts en PRO.
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
    </div>
  );
}
