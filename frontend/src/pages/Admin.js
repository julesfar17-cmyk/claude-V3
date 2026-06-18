import { useCallback, useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { toast } from "sonner";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import { useAuth } from "@/context/AuthContext";
import api, { formatApiErrorDetail } from "@/lib/api";

const fmt = (n, suffix = "") => `${n}${suffix}`;

export default function Admin() {
  const { user } = useAuth();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [newCode, setNewCode] = useState("");
  const [newDays, setNewDays] = useState(30);
  const [newMaxUses, setNewMaxUses] = useState("");

  const load = useCallback(async () => {
    try {
      const { data } = await api.get("/admin/stats");
      setStats(data);
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally {
      setLoading(false);
    }
  }, []);

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
              <Stat label="MRR" value={`${stats.mrr.toFixed(2)} €`} accent />
              <Stat label="Abonnés payants" value={fmt(stats.paid_users)} />
              <Stat label="Inscrits totaux" value={fmt(stats.total_users)} />
              <Stat label="Annulés" value={fmt(stats.canceled)} />
              <Stat label="Mensuel" value={fmt(stats.monthly_subscribers)} />
              <Stat label="Annuel" value={fmt(stats.yearly_subscribers)} />
              <Stat label="Connexion Google" value={fmt(stats.google_users)} />
              <Stat label="Connexion email" value={fmt(stats.password_users)} />
              <Stat label="Séparations / mois" value={fmt(stats.separations_this_month)} />
              <Stat label="Coût Replicate estimé" value={`${stats.estimated_separation_cost_eur.toFixed(2)} €`} accent />
            </div>

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
                    </tr>
                  </thead>
                  <tbody>
                    {stats.promo_codes.map((p) => (
                      <tr key={p.code} className="border-b border-border/50" data-testid={`admin-promo-row-${p.code}`}>
                        <td className="py-2 font-osd">{p.code}</td>
                        <td className="py-2">+{p.bonus_days} j</td>
                        <td className="py-2">{p.used_count || 0}</td>
                        <td className="py-2">{p.max_uses || "∞"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <section className="bg-card border border-border p-6 sm:p-8">
              <h2 className="font-display text-lg font-bold mb-4">Derniers inscrits</h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="font-osd text-[11px] tracking-wider text-muted-foreground border-b border-border">
                      <th className="text-left py-2">EMAIL</th>
                      <th className="text-left py-2">PROVIDER</th>
                      <th className="text-left py-2">STATUT</th>
                      <th className="text-left py-2">DATE</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stats.recent_users.map((u) => (
                      <tr key={u.user_id} className="border-b border-border/50">
                        <td className="py-2">{u.email}</td>
                        <td className="py-2">{u.auth_provider}</td>
                        <td className="py-2">{u.subscription?.status || "gratuit"}</td>
                        <td className="py-2 text-muted-foreground">
                          {new Date(u.created_at).toLocaleDateString("fr-FR")}
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
