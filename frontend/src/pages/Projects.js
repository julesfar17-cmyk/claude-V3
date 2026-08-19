import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { FolderOpen, Copy, Trash2, Film } from "lucide-react";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import api, { formatApiErrorDetail } from "@/lib/api";

export default function Projects() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const load = useCallback(async () => {
    try {
      const { data } = await api.get("/projects");
      setData(data);
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const duplicate = async (id) => {
    try {
      await api.post(`/projects/${id}/duplicate`);
      toast.success("Projet dupliqué");
      load();
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    }
  };

  const remove = async (id, title) => {
    if (!window.confirm(`Supprimer « ${title} » ? Les médias associés seront effacés.`)) return;
    try {
      await api.delete(`/projects/${id}`);
      toast.success("Projet supprimé");
      load();
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    }
  };

  const rename = async (p) => {
    const title = window.prompt("Nouveau titre :", p.title);
    if (!title || title === p.title) return;
    try {
      const { data: full } = await api.get(`/projects/${p.project_id}`);
      await api.post("/projects", { project_id: p.project_id, title, state: full.state });
      load();
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col">
      <Navbar />
      <main className="flex-1 mx-auto w-full max-w-6xl px-5 sm:px-8 py-12">
        <p className="font-osd text-xs tracking-[0.25em] text-primary mb-3">[ MES PROJETS ]</p>
        <div className="flex flex-wrap items-center justify-between gap-3 mb-10">
          <h1 className="font-display text-3xl sm:text-4xl font-extrabold tracking-tight">
            Mes projets{data ? ` (${data.count}${data.quota ? `/${data.quota}` : ""})` : ""}
          </h1>
          <Link
            to="/studio"
            data-testid="projects-new-button"
            className="bg-primary text-white font-bold px-5 py-2.5 text-sm hover:opacity-90 transition-colors"
          >
            + Nouveau projet
          </Link>
        </div>

        {loading ? (
          <p className="font-osd text-sm text-muted-foreground animate-pulse">CHARGEMENT…</p>
        ) : !data?.projects?.length ? (
          <div className="bg-card border border-border p-12 text-center" data-testid="projects-empty">
            <Film size={40} className="mx-auto text-muted-foreground mb-4" />
            <p className="text-muted-foreground mb-2">Aucun projet pour l'instant.</p>
            <p className="text-sm text-muted-foreground">
              Ouvre le studio, dépose un son : ton projet est sauvegardé automatiquement toutes les 30 secondes.
            </p>
          </div>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5" data-testid="projects-grid">
            {data.projects.map((p) => (
              <div key={p.project_id} className="bg-card border border-border overflow-hidden group" data-testid={`project-card-${p.project_id}`}>
                <button
                  onClick={() => navigate(`/studio?project=${p.project_id}`)}
                  className="block w-full aspect-[9/12] bg-secondary/40 relative overflow-hidden"
                  data-testid={`project-open-thumb-${p.project_id}`}
                >
                  {p.thumb ? (
                    <img src={p.thumb} alt={p.title} className="w-full h-full object-cover group-hover:scale-105 transition-transform" />
                  ) : (
                    <span className="absolute inset-0 flex items-center justify-center text-muted-foreground"><Film size={32} /></span>
                  )}
                </button>
                <div className="p-4">
                  <button onClick={() => rename(p)} className="font-display font-bold text-left w-full truncate hover:text-primary transition-colors" title="Renommer">
                    {p.title}
                  </button>
                  <p className="text-xs text-muted-foreground mt-1">
                    Modifié le {new Date(p.updated_at).toLocaleDateString("fr-FR")} à {new Date(p.updated_at).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}
                  </p>
                  <div className="flex gap-2 mt-4">
                    <button
                      onClick={() => navigate(`/studio?project=${p.project_id}`)}
                      data-testid={`project-open-${p.project_id}`}
                      className="flex-1 inline-flex items-center justify-center gap-1.5 bg-primary text-white text-xs font-bold px-3 py-2 hover:opacity-90 transition-colors"
                    >
                      <FolderOpen size={13} /> Ouvrir
                    </button>
                    <button
                      onClick={() => duplicate(p.project_id)}
                      data-testid={`project-duplicate-${p.project_id}`}
                      className="border border-border px-3 py-2 hover:border-foreground transition-colors" title="Dupliquer"
                    >
                      <Copy size={13} />
                    </button>
                    <button
                      onClick={() => remove(p.project_id, p.title)}
                      data-testid={`project-delete-${p.project_id}`}
                      className="border border-border px-3 py-2 text-primary hover:border-primary transition-colors" title="Supprimer"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
      <Footer />
    </div>
  );
}
