import { useCallback, useEffect, useState } from "react";
import api from "@/lib/api";

const EVENT_LABELS = {
  preview_stall: "Gels d'aperçu",
  frame_miss: "Replis vignette",
  decoder_error: "Erreurs décodeur",
  clip_not_ready: "Clip pas prêt",
};

export const PreviewTelemetryAdmin = () => {
  const [days, setDays] = useState(7);
  const [data, setData] = useState(null);

  const load = useCallback(async (d) => {
    try {
      const { data } = await api.get(`/admin/telemetry/preview?days=${d}`);
      setData(data);
    } catch {
      setData(null);
    }
  }, []);
  useEffect(() => { load(days); }, [days, load]);

  const Breakdown = ({ title, rows }) => (
    <div>
      <p className="font-osd text-[11px] tracking-widest text-muted-foreground mb-2">{title}</p>
      {Object.entries(rows || {}).length === 0 && <p className="text-xs text-muted-foreground">—</p>}
      {Object.entries(rows || {}).map(([k, v]) => (
        <p key={k} className="text-xs text-muted-foreground flex justify-between gap-3">
          <span className="truncate">{k}</span>
          <span className="text-foreground font-osd">
            {typeof v === "object" ? `${v.with_stall}/${v.sessions} gelées` : v}
          </span>
        </p>
      ))}
    </div>
  );

  return (
    <section className="bg-card border border-border p-6 sm:p-8 mb-8" data-testid="preview-telemetry-section">
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-display text-lg">Télémétrie aperçus (§2)</h2>
        <select value={days} onChange={(e) => setDays(+e.target.value)} data-testid="telemetry-days-select"
          className="bg-secondary border border-border text-xs px-2 py-1.5">
          <option value={3}>3 jours</option>
          <option value={7}>7 jours</option>
          <option value={30}>30 jours</option>
        </select>
      </div>
      {!data ? (
        <p className="text-sm text-muted-foreground">Chargement…</p>
      ) : data.total_sessions === 0 ? (
        <p className="text-sm text-muted-foreground" data-testid="telemetry-empty">
          Aucune donnée sur la période — les sondes tournent, laisse 3-5 jours de trafic avant de classifier (étape B).
        </p>
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div><p className="font-display text-2xl" data-testid="telemetry-sessions">{data.total_sessions}</p><p className="text-xs text-muted-foreground">sessions studio</p></div>
            <div><p className="font-display text-2xl text-primary">{data.pct_sessions_with_stall}%</p><p className="text-xs text-muted-foreground">avec ≥1 gel ({data.sessions_with_stall})</p></div>
            {Object.entries(data.event_counts).slice(0, 2).map(([k, v]) => (
              <div key={k}><p className="font-display text-2xl">{v}</p><p className="text-xs text-muted-foreground">{EVENT_LABELS[k] || k}</p></div>
            ))}
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
            <Breakdown title="PAR CAUSE" rows={Object.fromEntries(Object.entries(data.event_counts).map(([k, v]) => [EVENT_LABELS[k] || k, v]))} />
            <Breakdown title="PAR NAVIGATEUR" rows={data.by_browser} />
            <Breakdown title="PAR TAILLE DE PROJET" rows={data.by_project_size} />
            <Breakdown title="CODECS EN CAUSE" rows={data.stall_codecs} />
          </div>
        </div>
      )}
    </section>
  );
};
