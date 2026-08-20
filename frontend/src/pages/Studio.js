import { useEffect } from "react";
import { useSearchParams } from "react-router-dom";

const BUST = Date.now(); // anti-cache : garantit la dernière version du studio après chaque déploiement

export default function Studio() {
  const [params] = useSearchParams();
  useEffect(() => {
    // le studio (iframe) a son propre curseur V3 : on masque celui du parent
    document.body.classList.add("no-cur");
    return () => document.body.classList.remove("no-cur");
  }, []);
  const projectId = params.get("project");
  const sessionId = params.get("session_id");
  const qs = [
    projectId ? `project=${projectId}` : null,
    sessionId ? `session_id=${sessionId}` : null,
    `v=${BUST}`,
  ].filter(Boolean).join("&");
  return (
    <div className="h-screen w-full bg-background">
      <iframe
        src={`/studio.html?${qs}`}
        title="Studio BEATCUT"
        data-testid="studio-iframe"
        className="block w-full h-full border-0"
        allow="autoplay; clipboard-write"
      />
    </div>
  );
}
