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
  const [webhook, setWebhook] = useState(null);
  const [cancellations, setCancellations] = useState(null);

  const load = useCallback(async () => {
    try {
      const [{ data }, { data: usersData }, { data: wh }, { data: cancels }] = await Promise.all([
        api.get("/admin/stats"),
        api.get("/admin/users"),
        api.get("/admin/payments/webhook"),
        api.get("/admin/cancellations"),
      ]);
      setStats(data);
      setAllUsers(usersData);
      setWebhook(wh);
      setCancellations(cancels);
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
              <Stat label="En essai gratuit (7 j)" value={stats.stripe_trialing_subs != null ? fmt(stats.stripe_trialing_subs) : fmt(stats.trial_users || 0)} accent />
              <Stat
                label="Convertis depuis l'essai"
                value={`${fmt(stats.trial_converted || 0)}${stats.trial_conversion_rate != null ? ` (${stats.trial_conversion_rate} %)` : ""}`}
                accent
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
                          <td className="py-2 pr-4">{c.plan}</td>
                          <td className="py-2 pr-4">{c.canceled_at ? new Date(c.canceled_at).toLocaleDateString("fr-FR") : "—"}</td>
                          <td className="py-2 pr-4">{c.access_until ? new Date(c.access_until).toLocaleDateString("fr-FR") : "—"}</td>
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
