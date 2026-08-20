import { useCallback, useEffect } from "react";

const BUST = Date.now(); // anti-cache : garantit la dernière version de la landing après chaque déploiement

export default function Landing() {
  useEffect(() => {
    // la landing (iframe) a son propre curseur V3 : on masque celui du parent
    document.body.classList.add("no-cur");
    return () => document.body.classList.remove("no-cur");
  }, []);
  const onLoad = useCallback((e) => {
    try {
      const doc = e.target.contentDocument;
      doc.querySelectorAll('a[href^="/"]').forEach((a) => (a.target = "_top"));
    } catch {}
  }, []);
  return (
    <iframe
      src={`/landing.html?v=${BUST}`}
      title="BeatCut"
      data-testid="landing-iframe"
      onLoad={onLoad}
      style={{ position: "fixed", inset: 0, width: "100%", height: "100%", border: "none", background: "#000" }}
    />
  );
}
