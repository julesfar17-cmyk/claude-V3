import { Link, useSearchParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { Logo } from "@/components/Navbar";

const BUST = Date.now(); // anti-cache : garantit la dernière version du studio après chaque déploiement

export default function Studio() {
  const [params] = useSearchParams();
  const projectId = params.get("project");
  return (
    <div className="h-screen w-full flex flex-col bg-background">
      <div className="hidden sm:flex items-center justify-between px-4 sm:px-6 h-12 bg-[#0d0b11] border-b border-border shrink-0">
        <Link
          to="/dashboard"
          data-testid="studio-back-button"
          className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft size={16} /> Mon compte
        </Link>
        <Logo />
        <span className="font-osd text-[11px] tracking-[0.18em] text-[#d9ffd0] hidden sm:flex items-center gap-2">
          <span className="rec-dot" /> STUDIO
        </span>
      </div>
      <iframe
        src={projectId ? `/studio.html?project=${projectId}&v=${BUST}` : `/studio.html?v=${BUST}`}
        title="Studio BEATCUT"
        data-testid="studio-iframe"
        className="block w-full flex-1 border-0"
        allow="autoplay; clipboard-write"
      />
    </div>
  );
}
