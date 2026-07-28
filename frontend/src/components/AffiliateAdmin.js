import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import api, { formatApiErrorDetail } from "@/lib/api";

const PLANS = [
  { id: "pro_monthly", label: "PRO mensuel (19,99 €)" },
  { id: "pro_yearly", label: "PRO annuel (149 €)" },
  { id: "essentiel", label: "ESSENTIEL (9,99 €)" },
  { id: "studio", label: "STUDIO (499 €/an)" },
  { id: "monthly", label: "Legacy PRO (12,99 €)" },
  { id: "yearly", label: "Legacy PRO annuel (99 €)" },
  { id: "basic", label: "Legacy BASIC (6,99 €)" },
];
const eur = (c) => (c / 100).toFixed(2).replace(".", ",") + " €";

export const AffiliateAdmin = () => {
  const [codes, setCodes] = useState([]);
  const [code, setCode] = useState("");
  const [kind, setKind] = useState("amount");
  const [value, setValue] = useState("2");
  const [plans, setPlans] = useState(["pro_monthly"]);
  const [commission, setCommission] = useState("20");
  const [busy, setBusy] = useState(false);
  const [detail, setDetail] = useState(null);

  const load = useCallback(() => {
    api.get("/admin/affiliate").then(({ data }) => setCodes(data.codes)).catch(() => {});
  }, []);
  useEffect(load, [load]);

  const togglePlan = (p) => setPlans((cur) => (cur.includes(p) ? cur.filter((x) => x !== p) : [...cur, p]));

  const create = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const payload = { code: code.trim(), kind, plans, commission_pct: parseFloat(commission) || 0 };
      if (kind === "amount") payload.amount_off_cents = Math.round(parseFloat(value.replace(",", ".")) * 100);
      else payload.percent_off = parseFloat(value.replace(",", "."));
      await api.post("/admin/affiliate", payload);
      toast.success(`Code affilié ${code.trim().toUpperCase()} créé — remise Stripe à vie active ✓`);
      setCode("");
      load();
    } catch (e2) {
      toast.error(formatApiErrorDetail(e2.response?.data?.detail) || "Création impossible");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (c) => {
    if (!window.confirm(`Supprimer le code ${c} ? Les nouveaux clients ne pourront plus l'utiliser (les abonnés existants gardent leur remise). Le suivi de ce code sera effacé.`)) return;
    try {
      await api.delete(`/admin/affiliate/${c}`);
      toast.success(`Code ${c} supprimé`);
      load();
    } catch (e2) {
      toast.error(formatApiErrorDetail(e2.response?.data?.detail) || "Suppression impossible");
    }
  };

  return (
    <section className="bg-card border border-border p-6 sm:p-8 mb-8" data-testid="admin-affiliate-section">
      <h2 className="font-display text-lg font-bold mb-1">Codes affiliés (remise Stripe à vie)</h2>
      <p className="text-xs text-muted-foreground mb-5">
        La remise est appliquée automatiquement sur Stripe, sur tous les paiements, à vie. Lien à donner à l'affilié :
        <span className="font-osd"> {window.location.origin}/?promo=CODE</span>
      </p>
      <form onSubmit={create} className="flex flex-wrap items-end gap-3 mb-6">
        <div>
          <p className="font-osd text-[11px] text-muted-foreground mb-1">CODE</p>
          <input value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} placeholder="JULES10" data-testid="affiliate-code-input" className="bg-background border border-border px-3 py-2 text-sm w-32" />
        </div>
        <div>
          <p className="font-osd text-[11px] text-muted-foreground mb-1">TYPE</p>
          <select value={kind} onChange={(e) => setKind(e.target.value)} data-testid="affiliate-kind-select" className="bg-background border border-border px-3 py-2 text-sm">
            <option value="amount">Remise en €</option>
            <option value="percent">Remise en %</option>
          </select>
        </div>
        <div>
          <p className="font-osd text-[11px] text-muted-foreground mb-1">{kind === "amount" ? "€ DE REMISE / paiement" : "% DE REMISE"}</p>
          <input value={value} onChange={(e) => setValue(e.target.value)} data-testid="affiliate-value-input" className="bg-background border border-border px-3 py-2 text-sm w-24" />
        </div>
        <div>
          <p className="font-osd text-[11px] text-muted-foreground mb-1">% COMMISSION AFFILIÉ</p>
          <input value={commission} onChange={(e) => setCommission(e.target.value)} data-testid="affiliate-commission-input" className="bg-background border border-border px-3 py-2 text-sm w-20" />
        </div>
        <div>
          <p className="font-osd text-[11px] text-muted-foreground mb-1">PLANS CONCERNÉS</p>
          <div className="flex gap-3">
            {PLANS.map((p) => (
              <label key={p.id} className="flex items-center gap-1.5 text-xs cursor-pointer">
                <input type="checkbox" checked={plans.includes(p.id)} onChange={() => togglePlan(p.id)} data-testid={`affiliate-plan-${p.id}`} />
                {p.label}
              </label>
            ))}
          </div>
        </div>
        <button type="submit" disabled={busy || !code.trim() || !plans.length} data-testid="affiliate-create-btn" className="bg-primary text-white font-bold px-5 py-2.5 hover:bg-[#d32f2f] transition-colors disabled:opacity-50">
          Créer
        </button>
      </form>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="font-osd text-[11px] tracking-wider text-muted-foreground border-b border-border">
              <th className="text-left py-2">CODE</th>
              <th className="text-left py-2">REMISE</th>
              <th className="text-left py-2">PRIX APRÈS</th>
              <th className="text-left py-2">UTILISÉ</th>
              <th className="text-left py-2">ABONNÉS ACTIFS</th>
              <th className="text-left py-2">REVENU / MOIS</th>
              <th className="text-left py-2">COMMISSION / MOIS</th>
              <th className="text-left py-2"></th>
            </tr>
          </thead>
          <tbody>
            {codes.map((a) => (
              <tr key={a.code} className="border-b border-border/50" data-testid={`affiliate-row-${a.code}`}>
                <td className="py-2 font-osd">{a.code}</td>
                <td className="py-2">{a.kind === "percent" ? `−${a.percent_off} %` : `−${eur(a.amount_off_cents)}`} à vie</td>
                <td className="py-2 text-xs">
                  {Object.values(a.prices || {}).map((p) => (
                    <div key={p.label}><span className="text-muted-foreground line-through">{eur(p.base_cents)}</span> → <b>{eur(p.after_cents)}</b> <span className="text-muted-foreground">({p.label})</span></div>
                  ))}
                </td>
                <td className="py-2">{a.use_count || 0}</td>
                <td className="py-2">{a.active_subscribers}</td>
                <td className="py-2">{(a.monthly_revenue || 0).toFixed(2)} €</td>
                <td className="py-2 font-bold text-primary">{(a.monthly_commission || 0).toFixed(2)} € <span className="text-muted-foreground font-normal">({a.commission_pct} %)</span></td>
                <td className="py-2 text-right whitespace-nowrap">
                  {(a.uses || []).length > 0 && (
                    <button onClick={() => setDetail(detail === a.code ? null : a.code)} data-testid={`affiliate-detail-${a.code}`} className="text-xs underline underline-offset-2 mr-3">
                      {detail === a.code ? "masquer" : "détail"}
                    </button>
                  )}
                  <button onClick={() => remove(a.code)} data-testid={`affiliate-delete-${a.code}`} className="text-xs text-primary hover:underline">supprimer</button>
                </td>
              </tr>
            ))}
            {!codes.length && (
              <tr><td colSpan={8} className="py-4 text-muted-foreground text-xs">Aucun code affilié pour l'instant.</td></tr>
            )}
          </tbody>
        </table>
        {codes.filter((a) => a.code === detail).map((a) => (
          <div key={a.code} className="mt-3 bg-background border border-border p-4 text-xs" data-testid={`affiliate-uses-${a.code}`}>
            <p className="font-osd text-[11px] text-muted-foreground mb-2">ABONNÉS VIA {a.code}</p>
            {(a.uses || []).map((u, i) => (
              <div key={i} className="flex gap-4 py-1 border-b border-border/40">
                <span className="flex-1">{u.email || u.user_id}</span>
                <span>{u.plan}</span>
                <span className="text-muted-foreground">{u.date ? new Date(u.date).toLocaleDateString("fr-FR") : ""}</span>
              </div>
            ))}
          </div>
        ))}
      </div>
    </section>
  );
};
