import { useCallback, useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { toast } from "sonner";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import { useAuth } from "@/context/AuthContext";
import api, { formatApiErrorDetail } from "@/lib/api";
import { AffiliateAdmin } from "@/components/AffiliateAdmin";
import { PreviewTelemetryAdmin } from "@/components/PreviewTelemetryAdmin";

const fmt = (n, suffix = "") => `${n}${suffix}`;

const REASON_LABELS = {
  too_expensive: "💸 Trop cher",
  not_enough_use: "🕒 Pas assez utilisé",
  missing_features: "🧩 Fonctionnalités manquantes",
  technical_issues: "🐞 Problèmes techniques",
  promo_done: "🎤 Promo terminée",
  other: "🤷 Autre",
};

const ONB_QUESTIONS = {
  persona: "Tu es plutôt...",
  genre: "Ton style principal ?",
  release_timing: "Tu sors un son quand ?",
  current_method: "Tes vidéos de promo aujourd'hui ?",
  source: "Comment ils nous ont trouvés ?",
};
const ONB_ANSWER_LABELS = {
  artiste: "🎤 Artiste", beatmaker: "🎹 Beatmaker/prod", manager: "📱 Manager/label", createur: "🎬 Créateur de contenu",
  rap_drill: "Rap / Drill", plugg_hyperpop: "Plugg / Cloud / Hyperpop", afro_shatta: "Afro / Shatta",
  pop_chanson: "Pop / Chanson", electro_club: "Électro / Club", autre: "Autre",
  cette_semaine: "🔥 Cette semaine", ce_mois: "📅 Ce mois-ci", plusieurs: "🎧 Plusieurs en préparation", pas_de_date: "💭 Pas de date",
  capcut: "✂️ CapCut / à la main", pochette: "🖼 Pochette fixe", rarement: "🤷 Poste rarement", debute: "🚀 Débute",
  tiktok: "TikTok", bouche_a_oreille: "Bouche à oreille", instagram: "Instagram", communautes: "Discord / Facebook", google: "Google",
};

export default function Admin() {
  const { user } = useAuth();
  const [stats, setStats] = useState(null);
  const [allUsers, setAllUsers] = useState(null);
  const [loading, setLoading] = useState(true);
  const [newCode, setNewCode] = useState("");
  const [newDays, setNewDays] = useState(30);
  const [newMaxUses, setNewMaxUses] = useState("");
  const [reconciling, setReconciling] = useState(false);
  const [reconcileResult, setReconcileResult] = useState(null);
  const [cleaning, setCleaning] = useState(false);
  const [cleanupResult, setCleanupResult] = useState(null);
  const [webhook, setWebhook] = useState(null);
  const [cancellations, setCancellations] = useState(null);
  const [onbStats, setOnbStats] = useState(null);

  const load = useCallback(async () => {
    try {
      const [{ data }, { data: usersData }, { data: wh }, { data: cancels }, { data: onb }] = await Promise.all([
        api.get("/admin/stats"),
        api.get("/admin/users"),
        api.get("/admin/payments/webhook"),
        api.get("/admin/cancellations"),
        api.get("/admin/onboarding-stats"),
      ]);
      setStats(data);
      setAllUsers(usersData);
      setWebhook(wh);
      setCancellations(cancels);
      setOnbStats(onb);
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally {
      setLoading(false);
    }
  }, []);

  const reconcile = async () => {
    setReconciling(true);
    try {
      const { data } = await api.post("/admin/payments/reconcile");
      setReconcileResult(data);
      const n = data.payments.activated;
      toast.success(n ? `${n} accès activé(s) rétroactivement !` : "Aucun paiement en attente — tout est à jour");
      load();
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally {
      setReconciling(false);
    }
  };

  const [custEmail, setCustEmail] = useState("");
  const [cust, setCust] = useState(null);
  const [custBusy, setCustBusy] = useState(false);
  const [custArm, setCustArm] = useState(false);
  const [refundArm, setRefundArm] = useState(false);

  const searchCustomer = async (e) => {
    e && e.preventDefault();
    if (!custEmail.trim()) return;
    setCustBusy(true); setCustArm(false); setRefundArm(false);
    try {
      const { data } = await api.get("/admin/customer", { params: { email: custEmail.trim() } });
      setCust(data);
    } catch (err) {
      setCust(null);
      toast.error(formatApiErrorDetail(err.response?.data?.detail) || "Client introuvable");
    } finally {
      setCustBusy(false);
    }
  };

  const cancelCustomer = async () => {
    setCustBusy(true);
    try {
      const { data } = await api.post("/admin/customer/cancel", { email: cust.email });
      toast.success(data.message);
      setCustArm(false);
      await searchCustomer();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setCustBusy(false);
    }
  };

  const refundCustomer = async () => {
    setCustBusy(true);
    try {
      const { data } = await api.post("/admin/customer/refund", { email: cust.email });
      toast.success(data.message);
      setRefundArm(false);
      await searchCustomer();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setCustBusy(false);
    }
  };

  const cleanupMedia = async () => {
    setCleaning(true);
    try {
      const { data } = await api.post("/admin/media/cleanup");
      setCleanupResult(data);
      toast.success(data.deleted ? `${data.deleted} fichier(s) orphelin(s) supprimé(s) — ${(data.freed_bytes / 1e6).toFixed(1)} Mo libérés` : "Aucun orphelin — le stockage est propre ✓");
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally {
      setCleaning(false);
    }
  };

  const setupWebhook = async () => {
    try {
      const { data } = await api.post("/admin/payments/webhook-setup");
      setWebhook(data);
      toast.success(data.already ? "Webhook déjà configuré ✓" : "Webhook Stripe créé — activations instantanées ✓");
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    }
  };

  const copyAllEmails = () => {
    if (!allUsers?.users?.length) return;
    const emails = allUsers.users.map((u) => u.email).filter(Boolean).join(", ");
    navigator.clipboard.writeText(emails).then(
      () => toast.success(`${allUsers.users.length} emails copiés dans le presse-papier`),
      () => toast.error("Impossible de copier — sélectionne manuellement"),
    );
  };

  useEffect(() => {
    if (user?.role === "admin") load();
  }, [user, load]);

  const createPromo = async (e) => {
    e.preventDefault();
    try {
      await api.post("/admin/promo", {
        code: newCode,
        bonus_days: Number(newDays),
        max_uses: newMaxUses ? Number(newMaxUses) : null,
      });
      toast.success(`Code "${newCode.toUpperCase()}" créé`);
      setNewCode("");
      setNewMaxUses("");
      load();
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    }
  };

  if (user && user.role !== "admin") return <Navigate to="/dashboard" replace />;

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col">
      <Navbar />
      <main className="flex-1 mx-auto w-full max-w-6xl px-5 sm:px-8 py-12">
        <p className="font-osd text-xs tracking-[0.25em] text-primary mb-3">[ ADMIN ]</p>
        <h1 className="font-display text-3xl sm:text-4xl font-extrabold tracking-tight mb-10">
          Tableau de bord
        </h1>

        {loading || !stats ? (
          <p className="font-osd text-sm text-muted-foreground animate-pulse">CHARGEMENT…</p>
        ) : (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-10">
              <Stat label="MRR RÉEL (STRIPE)" value={stats.stripe_mrr != null ? `${stats.stripe_mrr.toFixed(2)} €` : `${stats.mrr.toFixed(2)} € (estimé)`} accent />
              <Stat label="ENCAISSÉ CE MOIS" value={stats.revenue_this_month != null ? `${stats.revenue_this_month.toFixed(2)} €` : "—"} accent />
              <Stat label="ENCAISSÉ TOTAL" value={stats.revenue_total != null ? `${stats.revenue_total.toFixed(2)} €` : "—"} accent />
              <Stat label="Abonnés actifs (payants réels)" value={stats.stripe_active_subs != null ? fmt(stats.stripe_active_subs) : fmt(stats.real_paid_users)} accent />
              <Stat label="En essai gratuit" value={stats.stripe_trialing_subs != null ? fmt(stats.stripe_trialing_subs) : fmt(stats.trial_users || 0)} accent />
              <Stat
                label="Convertis depuis l'essai"
                value={`${fmt(stats.trial_converted || 0)}${stats.trial_conversion_rate != null ? ` (${stats.trial_conversion_rate} %)` : ""}`}
                accent
              />
              <Stat
                label="Conversion essais 7 j vs 3 j"
                value={`${stats.trial_cohorts?.d7?.rate != null ? `${stats.trial_cohorts.d7.rate} %` : "—"} (${fmt(stats.trial_cohorts?.d7?.converted || 0)}/${fmt(stats.trial_cohorts?.d7?.started || 0)}) · ${stats.trial_cohorts?.d3?.rate != null ? `${stats.trial_cohorts.d3.rate} %` : "—"} (${fmt(stats.trial_cohorts?.d3?.converted || 0)}/${fmt(stats.trial_cohorts?.d3?.started || 0)})`}
              />
              <Stat label="Payants réels (Stripe)" value={fmt(stats.real_paid_users)} />
              <Stat label="Actifs via promo / offert" value={fmt(stats.promo_active_users)} />
              <Stat label="Inscrits totaux" value={fmt(stats.total_users)} />
              <Stat label="Essentiel (9,99 €)" value={fmt(stats.plans?.essentiel ?? 0)} />
              <Stat label="Pro (19,99 €)" value={fmt(stats.plans?.pro_monthly ?? 0)} />
              <Stat label="Pro annuel (149 €)" value={fmt(stats.plans?.pro_yearly ?? 0)} />
              <Stat label="Studio (499 €)" value={fmt(stats.plans?.studio ?? 0)} />
              <Stat label="Ancien Basic (6,99 €)" value={fmt(stats.plans?.basic ?? stats.basic_subscribers)} />
              <Stat label="Ancien Pro (12,99 €)" value={fmt(stats.plans?.monthly ?? stats.monthly_subscribers)} />
              <Stat label="Ancien Pro annuel (99 €)" value={fmt(stats.plans?.yearly ?? stats.yearly_subscribers)} />
              <Stat label="Annulés" value={fmt(stats.canceled)} />
              <Stat label="Connexion Google" value={fmt(stats.google_users)} />
              <Stat label="Connexion email" value={fmt(stats.password_users)} />
              <Stat label="Séparations / mois" value={fmt(stats.separations_this_month)} />
              <Stat label="Coût Replicate estimé" value={`${stats.estimated_separation_cost_eur.toFixed(2)} €`} />
            </div>

            <section className="bg-card border border-border p-6 sm:p-8 mb-8">
              <h2 className="font-display text-lg font-bold mb-2">Paiements &amp; abonnements</h2>
              <p className="text-xs text-muted-foreground mb-4 max-w-2xl">
                La réconciliation active les paiements Stripe encaissés mais jamais réclamés (client parti avant le
                retour sur le site) et vérifie que les annulations sont bien effectives. Elle tourne aussi
                automatiquement toutes les 10 minutes. Le webhook Stripe rend les activations instantanées.
              </p>
              <div className="flex flex-wrap gap-3 items-center">
                <button
                  onClick={reconcile}
                  disabled={reconciling}
                  data-testid="admin-reconcile-button"
                  className="bg-primary text-white font-bold px-5 py-2.5 hover:bg-[#d32f2f] transition-colors disabled:opacity-50"
                >
                  {reconciling ? "Vérification Stripe…" : "🔁 Réconcilier maintenant"}
                </button>
                <button
                  onClick={setupWebhook}
                  data-testid="admin-webhook-setup-button"
                  className="border border-border px-4 py-2.5 text-xs font-osd tracking-wider hover:border-foreground transition-colors"
                >
                  {webhook?.configured ? "WEBHOOK STRIPE ✓ ACTIF" : "⚡ ACTIVER LE WEBHOOK STRIPE"}
                </button>
              </div>
              {webhook?.url && (
                <p className="mt-2 text-xs text-muted-foreground font-osd" data-testid="admin-webhook-url">{webhook.url}</p>
              )}
              {reconcileResult && (
                <div className="mt-4 text-sm space-y-1" data-testid="admin-reconcile-result">
                  <p>
                    Paiements vérifiés : {reconcileResult.payments.checked} —{" "}
                    <span className="text-primary font-bold">{reconcileResult.payments.activated} accès activé(s)</span>
                    {reconcileResult.payments.activated_emails?.length > 0 &&
                      ` (${reconcileResult.payments.activated_emails.join(", ")})`}
                  </p>
                  <p>
                    Abonnements vérifiés : {reconcileResult.subscriptions.checked} —{" "}
                    {reconcileResult.subscriptions.status_changed} statut(s) mis à jour
                    {(reconcileResult.subscriptions.changes || [])
                      .map((c) => ` · ${c.email} : ${c.avant || "?"} → ${c.apres}`)
                      .join("")}
                  </p>
                </div>
              )}
            </section>

            <section className="bg-card border border-border p-6 sm:p-8 mb-8" data-testid="admin-cancellations-section">
              <h2 className="font-display text-lg font-bold mb-2">Suivi des annulations</h2>
              <p className="text-xs text-muted-foreground mb-4">
                Qui a annulé son abonnement (ou son essai), quand, et jusqu'à quand son accès court encore.
              </p>
              {!cancellations?.cancellations?.length ? (
                <p className="text-sm text-muted-foreground" data-testid="admin-cancellations-empty">Aucune annulation pour l'instant 🎉</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left font-osd text-[11px] text-muted-foreground border-b border-border">
                        <th className="py-2 pr-4">EMAIL</th>
                        <th className="py-2 pr-4">PLAN</th>
                        <th className="py-2 pr-4">ANNULÉ LE</th>
                        <th className="py-2 pr-4">ACCÈS JUSQU'AU</th>
                        <th className="py-2">STATUT</th>
                      </tr>
                    </thead>
                    <tbody>
                      {cancellations.cancellations.map((c, i) => (
                        <tr key={i} className="border-b border-border/50" data-testid={`admin-cancel-row-${i}`}>
                          <td className="py-2 pr-4">{c.email}</td>
                          <td className="py-2 pr-4">
                            {c.was_trial ? <span className="text-[#8f9bff]">Essai Pro (avant débit)</span> : c.plan}
                          </td>
                          <td className="py-2 pr-4">{c.canceled_at ? new Date(c.canceled_at).toLocaleDateString("fr-FR") : "—"}</td>
                          <td className="py-2 pr-4">{c.was_trial ? "—" : c.access_until ? new Date(c.access_until).toLocaleDateString("fr-FR") : "—"}</td>
                          <td className="py-2">
                            {c.state === "access_until_end" ? (
                              <span className="text-[#ffd97a]">Accès encore actif</span>
                            ) : (
                              <span className="text-muted-foreground">Terminé</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            <section className="bg-card border border-border p-6 sm:p-8 mb-8" data-testid="admin-cancel-feedback-section">
              <h2 className="font-display text-lg font-bold mb-2">Pourquoi ils annulent</h2>
              <p className="text-xs text-muted-foreground mb-4">
                Réponses du formulaire d'annulation (en %) + efficacité de l'offre de rétention −50 %.
              </p>
              {!stats.cancel_feedback?.total ? (
                <p className="text-sm text-muted-foreground" data-testid="admin-cancel-feedback-empty">
                  Aucune réponse pour l'instant — les données arriveront avec les premières annulations.
                </p>
              ) : (
                <>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
                    <Stat label="Réponses au formulaire" value={fmt(stats.cancel_feedback.total)} />
                    <Stat
                      label="Restés grâce à l'offre −50 %"
                      value={`${fmt(stats.cancel_feedback.retained)}${stats.cancel_feedback.retained_pct != null ? ` (${stats.cancel_feedback.retained_pct} %)` : ""}`}
                      accent
                    />
                    <Stat label="Partis quand même" value={fmt(stats.cancel_feedback.lost)} />
                  </div>
                  <div className="space-y-2 max-w-xl">
                    {Object.entries(stats.cancel_feedback.reasons || {})
                      .sort((a, b) => b[1].count - a[1].count)
                      .map(([reason, r]) => (
                        <div key={reason} data-testid={`admin-cancel-reason-${reason}`}>
                          <div className="flex items-center justify-between text-sm mb-1">
                            <span>{REASON_LABELS[reason] || reason}</span>
                            <span className="font-osd text-[#8f9bff]">{r.pct} % ({r.count})</span>
                          </div>
                          <div className="h-2 bg-secondary overflow-hidden">
                            <div className="h-full bg-[#8f9bff]" style={{ width: `${r.pct}%` }} />
                          </div>
                        </div>
                      ))}
                  </div>
                  {stats.cancel_feedback.recent?.some((f) => f.comment) && (
                    <div className="mt-6">
                      <p className="font-osd text-[11px] text-muted-foreground mb-2">DERNIERS COMMENTAIRES</p>
                      <div className="space-y-2">
                        {stats.cancel_feedback.recent.filter((f) => f.comment).slice(0, 8).map((f, i) => (
                          <p key={i} className="text-sm text-muted-foreground border-l-2 border-border pl-3">
                            « {f.comment} » — <span className="text-foreground">{f.email}</span>{" "}
                            ({REASON_LABELS[f.reason] || f.reason}{f.retained === true ? " · resté ✦" : f.retained === false ? " · parti" : ""})
                          </p>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              )}
            </section>

            <section className="bg-card border border-border p-6 sm:p-8 mb-8" data-testid="admin-customer-section">
              <h2 className="font-display text-lg font-bold mb-4">Rechercher un client</h2>
              <form onSubmit={searchCustomer} className="flex gap-3 flex-wrap">
                <input
                  type="email"
                  value={custEmail}
                  onChange={(e) => setCustEmail(e.target.value)}
                  placeholder="email@client.com"
                  data-testid="admin-customer-search-input"
                  className="flex-1 min-w-[240px] bg-background border border-border px-4 py-2.5 text-sm focus:border-[#d9ffd0] focus:outline-none"
                />
                <button type="submit" disabled={custBusy} data-testid="admin-customer-search-button"
                  className="border border-border px-5 py-2.5 text-xs font-osd tracking-wider hover:border-foreground transition-colors disabled:opacity-50">
                  {custBusy ? "…" : "🔎 RECHERCHER"}
                </button>
              </form>
              {cust && (
                <div className="mt-6" data-testid="admin-customer-card">
                  <div className="grid sm:grid-cols-2 gap-x-8 gap-y-2 text-sm">
                    <p><span className="text-muted-foreground">Client :</span> <b>{cust.name}</b> — {cust.email}</p>
                    <p><span className="text-muted-foreground">Inscrit le :</span> {cust.created_at ? new Date(cust.created_at).toLocaleDateString("fr-FR") : "—"} ({cust.provider})</p>
                    <p data-testid="admin-customer-plan">
                      <span className="text-muted-foreground">Abonnement :</span>{" "}
                      <b>{cust.subscription?.plan || "aucun"}</b> · statut {cust.subscription?.status || "—"} · tier {cust.subscription?.tier}
                      {cust.subscription?.trial ? " · EN ESSAI" : ""}
                    </p>
                    <p><span className="text-muted-foreground">Accès jusqu'au :</span> {cust.subscription?.current_period_end ? new Date(cust.subscription.current_period_end).toLocaleDateString("fr-FR") : "—"}</p>
                    <p><span className="text-muted-foreground">Stripe :</span> {cust.stripe_subscription_id ? `${cust.stripe_state?.status || "?"}${cust.stripe_state?.cancel_at_period_end ? " (annulé fin de période)" : ""}` : "aucun abonnement Stripe"}</p>
                    <p><span className="text-muted-foreground">Promo :</span> {cust.promo_applied ? `${cust.promo_applied}${cust.promo_pro_until ? ` → ${new Date(cust.promo_pro_until).toLocaleDateString("fr-FR")}` : ""}` : "—"}</p>
                  </div>
                  <p className="font-osd text-[11px] tracking-wider text-muted-foreground mt-5 mb-2">PAIEMENTS ({cust.payments.length})</p>
                  {cust.payments.length === 0 ? (
                    <p className="text-sm text-muted-foreground">Aucun paiement.</p>
                  ) : (
                    <div className="max-h-[220px] overflow-y-auto border border-border" data-testid="admin-customer-payments">
                      <table className="w-full text-xs">
                        <thead><tr className="text-left text-muted-foreground">
                          <th className="px-3 py-2">Date</th><th className="px-3 py-2">Plan</th><th className="px-3 py-2">Montant</th><th className="px-3 py-2">Statut</th>
                        </tr></thead>
                        <tbody>
                          {cust.payments.map((p, i) => (
                            <tr key={i} className="border-t border-border">
                              <td className="px-3 py-2">{p.created_at ? new Date(p.created_at).toLocaleDateString("fr-FR") : "—"}</td>
                              <td className="px-3 py-2">{p.plan}{p.with_trial ? " (essai)" : ""}{p.affiliate_code ? ` · code ${p.affiliate_code}` : ""}</td>
                              <td className="px-3 py-2">{p.amount != null ? `${p.amount.toFixed(2)} €` : "—"}</td>
                              <td className="px-3 py-2">{p.payment_status}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                  {(cust.stripe_subscription_id || cust.subscription?.is_pro || cust.stripe_customer_id) && (
                    <div className="mt-5 flex flex-col gap-3">
                      {cust.stripe_customer_id && (
                        !refundArm ? (
                          <div>
                            <button onClick={() => setRefundArm(true)} data-testid="admin-refund-customer-button"
                              className="border border-border px-4 py-2.5 text-xs font-osd tracking-wider hover:border-foreground transition-colors">
                              💶 REMBOURSER LE DERNIER PAIEMENT
                            </button>
                          </div>
                        ) : (
                          <div className="flex items-center gap-3 flex-wrap">
                            <span className="text-sm">Rembourser intégralement son dernier paiement Stripe ?</span>
                            <button onClick={refundCustomer} disabled={custBusy} data-testid="admin-refund-customer-confirm"
                              className="bg-foreground text-background px-4 py-2.5 text-xs font-bold disabled:opacity-50">
                              {custBusy ? "…" : "OUI, REMBOURSER"}
                            </button>
                            <button onClick={() => setRefundArm(false)} className="text-xs text-muted-foreground underline">Non</button>
                          </div>
                        )
                      )}
                      {(cust.stripe_subscription_id || cust.subscription?.is_pro) && (!custArm ? (
                        <div>
                          <button onClick={() => setCustArm(true)} data-testid="admin-cancel-customer-button"
                            className="border border-primary text-primary px-4 py-2.5 text-xs font-osd tracking-wider hover:bg-primary hover:text-white transition-colors">
                            🛑 ANNULER SON ABONNEMENT IMMÉDIATEMENT
                          </button>
                        </div>
                      ) : (
                        <div className="flex items-center gap-3 flex-wrap">
                          <span className="text-sm text-primary">Confirmer ? Accès coupé tout de suite, plus aucun prélèvement futur.</span>
                          <button onClick={cancelCustomer} disabled={custBusy} data-testid="admin-cancel-customer-confirm"
                            className="bg-primary text-white px-4 py-2.5 text-xs font-bold disabled:opacity-50">
                            {custBusy ? "…" : "OUI, ANNULER"}
                          </button>
                          <button onClick={() => setCustArm(false)} className="text-xs text-muted-foreground underline">Non</button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </section>

            <section className="bg-card border border-border p-6 sm:p-8 mb-8" data-testid="admin-storage-section">
              <h2 className="font-display text-lg font-bold mb-2">Stockage (GridFS)</h2>
              <p className="text-xs text-muted-foreground mb-4 max-w-2xl">
                Supprime les fichiers médias que plus aucun projet, sauvegarde ou watermark ne référence
                (marge de sécurité : 24 h). Tourne aussi automatiquement une fois par jour.
              </p>
              <button
                onClick={cleanupMedia}
                disabled={cleaning}
                data-testid="admin-media-cleanup-button"
                className="border border-border px-4 py-2.5 text-xs font-osd tracking-wider hover:border-foreground transition-colors disabled:opacity-50"
              >
                {cleaning ? "Nettoyage en cours…" : "🧹 NETTOYER MAINTENANT"}
              </button>
              {cleanupResult && (
                <p className="mt-3 text-sm" data-testid="admin-media-cleanup-result">
                  {cleanupResult.scanned} fichiers scannés · {cleanupResult.referenced} référencés ·{" "}
                  <span className="text-primary font-bold">{cleanupResult.deleted} orphelin(s) supprimé(s)</span>
                  {" "}({(cleanupResult.freed_bytes / 1e6).toFixed(1)} Mo libérés)
                </p>
              )}
            </section>

            <section className="bg-card border border-border p-6 sm:p-8 mb-8" data-testid="admin-onboarding-section">
              <h2 className="font-display text-lg font-bold mb-2">Onboarding & tutoriel</h2>
              <p className="text-xs text-muted-foreground mb-4">
                Funnel du tutoriel studio (mobile + PC) et réponses au questionnaire d'inscription.
              </p>
              {onbStats && (
                <>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6" data-testid="admin-tuto-stats">
                    <Stat label="Tuto démarrés" value={fmt(onbStats.tuto.started)} />
                    <Stat label="Tuto terminés" value={`${fmt(onbStats.tuto.done)}${onbStats.tuto.completion_pct != null ? ` (${onbStats.tuto.completion_pct} %)` : ""}`} accent />
                    <Stat label="Tuto passés (skip)" value={fmt(onbStats.tuto.skipped)} />
                    <Stat label="Questionnaire terminé / passé" value={`${fmt(onbStats.form.done)} / ${fmt(onbStats.form.skipped)}`} />
                  </div>
                  <div className="grid md:grid-cols-2 gap-x-10 gap-y-6">
                    {Object.entries(onbStats.answers || {}).map(([field, a]) => (
                      <div key={field} data-testid={`admin-onb-question-${field}`}>
                        <p className="font-osd text-[11px] tracking-wider text-muted-foreground mb-2">
                          {ONB_QUESTIONS[field] || field} <span className="text-foreground">({a.total})</span>
                        </p>
                        {!a.total ? (
                          <p className="text-sm text-muted-foreground">Aucune réponse pour l'instant.</p>
                        ) : (
                          <div className="space-y-2">
                            {Object.entries(a.options)
                              .sort((x, y) => y[1].count - x[1].count)
                              .map(([opt, r]) => (
                                <div key={opt}>
                                  <div className="flex items-center justify-between text-sm mb-1">
                                    <span>{ONB_ANSWER_LABELS[opt] || opt}</span>
                                    <span className="font-osd text-[#d9ffd0]">{r.pct} % ({r.count})</span>
                                  </div>
                                  <div className="h-2 bg-secondary overflow-hidden">
                                    <div className="h-full bg-[#d9ffd0]" style={{ width: `${r.pct}%` }} />
                                  </div>
                                </div>
                              ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </>
              )}
            </section>

            <section className="bg-card border border-border p-6 sm:p-8 mb-8">
              <h2 className="font-display text-lg font-bold mb-4">Créer un code promo</h2>
              <form onSubmit={createPromo} className="flex flex-wrap gap-3 items-end">
                <div>
                  <p className="font-osd text-[11px] text-muted-foreground mb-1">CODE</p>
                  <input value={newCode} onChange={(e) => setNewCode(e.target.value)} placeholder="EX: FRIDAY" data-testid="admin-promo-code" className="bg-background border border-border px-3 py-2 text-sm" required minLength={3} />
                </div>
                <div>
                  <p className="font-osd text-[11px] text-muted-foreground mb-1">JOURS</p>
                  <input type="number" min={1} max={365} value={newDays} onChange={(e) => setNewDays(e.target.value)} data-testid="admin-promo-days" className="bg-background border border-border px-3 py-2 text-sm w-24" />
                </div>
                <div>
                  <p className="font-osd text-[11px] text-muted-foreground mb-1">MAX (vide = ∞)</p>
                  <input type="number" min={1} value={newMaxUses} onChange={(e) => setNewMaxUses(e.target.value)} data-testid="admin-promo-maxuses" className="bg-background border border-border px-3 py-2 text-sm w-24" />
                </div>
                <button type="submit" data-testid="admin-promo-create" className="bg-primary text-white font-bold px-5 py-2.5 hover:bg-[#d32f2f] transition-colors">
                  Créer
                </button>
              </form>
            </section>

            <section className="bg-card border border-border p-6 sm:p-8 mb-8">
              <h2 className="font-display text-lg font-bold mb-4">Codes promo existants</h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="font-osd text-[11px] tracking-wider text-muted-foreground border-b border-border">
                      <th className="text-left py-2">CODE</th>
                      <th className="text-left py-2">JOURS</th>
                      <th className="text-left py-2">UTILISÉ</th>
                      <th className="text-left py-2">MAX</th>
                      <th className="text-left py-2"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {stats.promo_codes.map((p) => (
                      <tr key={p.code} className="border-b border-border/50" data-testid={`admin-promo-row-${p.code}`}>
                        <td className="py-2 font-osd">{p.code}</td>
                        <td className="py-2">+{p.bonus_days} j</td>
                        <td className="py-2">{p.used_count || 0}</td>
                        <td className="py-2">{p.max_uses || "∞"}</td>
                        <td className="py-2 text-right">
                          <button
                            onClick={async () => {
                              if (!window.confirm(`Supprimer le code ${p.code} ?`)) return;
                              try {
                                await api.delete(`/admin/promo/${p.code}`);
                                toast.success(`Code ${p.code} supprimé`);
                                load();
                              } catch (e2) {
                                toast.error(formatApiErrorDetail(e2.response?.data?.detail) || "Suppression impossible");
                              }
                            }}
                            data-testid={`admin-promo-delete-${p.code}`}
                            className="text-xs text-primary hover:underline"
                          >
                            supprimer
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <AffiliateAdmin />

            <PreviewTelemetryAdmin />

            <section className="bg-card border border-border p-6 sm:p-8">
              <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
                <h2 className="font-display text-lg font-bold" data-testid="admin-all-users-title">
                  Tous les inscrits{allUsers ? ` (${allUsers.count})` : ""}
                </h2>
                <button
                  onClick={copyAllEmails}
                  data-testid="admin-copy-emails-button"
                  className="border border-border px-4 py-2 text-xs font-osd tracking-wider hover:border-foreground transition-colors"
                >
                  COPIER TOUS LES EMAILS
                </button>
              </div>
              <div className="overflow-x-auto max-h-[480px] overflow-y-auto" data-testid="admin-all-users-table">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-card">
                    <tr className="font-osd text-[11px] tracking-wider text-muted-foreground border-b border-border">
                      <th className="text-left py-2">EMAIL</th>
                      <th className="text-left py-2">PLAN</th>
                      <th className="text-left py-2">PAYANT</th>
                      <th className="text-left py-2">PROMO</th>
                      <th className="text-left py-2">PROVIDER</th>
                      <th className="text-left py-2">DATE</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(allUsers?.users || []).map((u) => (
                      <tr key={u.email} className="border-b border-border/50">
                        <td className="py-2">{u.email}</td>
                        <td className="py-2">
                          <span className={`font-osd text-[10px] tracking-wider px-2 py-0.5 ${
                            u.tier === "pro" ? "bg-primary/15 text-primary" :
                            u.tier === "basic" ? "bg-[#8f9bff]/15 text-[#8f9bff]" :
                            "bg-secondary text-muted-foreground"
                          }`}>
                            {u.tier === "free" ? "GRATUIT" : (u.plan || u.tier).toUpperCase()}
                          </span>
                        </td>
                        <td className="py-2">{u.paying ? "✓ Stripe" : u.tier !== "free" ? "offert" : "—"}</td>
                        <td className="py-2 font-osd text-xs">{u.promo || "—"}</td>
                        <td className="py-2 text-muted-foreground">{u.provider}</td>
                        <td className="py-2 text-muted-foreground">
                          {u.created_at ? new Date(u.created_at).toLocaleDateString("fr-FR") : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <p className="mt-8 text-xs text-muted-foreground">
              <Link to="/dashboard" className="underline underline-offset-4">← Retour au compte</Link>
            </p>
          </>
        )}
      </main>
      <Footer />
    </div>
  );
}

function Stat({ label, value, accent = false }) {
  return (
    <div className={`bg-card border ${accent ? "border-primary" : "border-border"} p-5`}>
      <p className="font-osd text-[10px] tracking-[0.18em] text-muted-foreground mb-2">{label}</p>
      <p className={`font-display text-2xl font-extrabold ${accent ? "text-primary" : ""}`}>{value}</p>
    </div>
  );
}
