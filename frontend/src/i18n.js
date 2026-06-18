// i18n minimaliste — FR (par défaut) / EN. Stocké dans localStorage.
import { createContext, useContext, useEffect, useState } from "react";

const STORAGE_KEY = "beatcut_lang";

const T = {
  fr: {
    "nav.features": "Fonctionnalités",
    "nav.how": "Comment ça marche",
    "nav.pricing": "Tarifs",
    "nav.login": "Se connecter",
    "nav.register": "Commencer gratuitement",
    "nav.account": "Mon compte",
    "nav.openStudio": "Ouvrir le studio",
    "nav.logout": "Se déconnecter",
    "hero.tag": "STUDIO BEAT-SYNC — 100% DANS TON NAVIGATEUR",
    "hero.title1": "Des vidéos calées",
    "hero.title2": "sur le beat.",
    "hero.title3": "En 60 secondes.",
    "hero.desc": "Dépose ton track, ajoute tes clips : BEATCUT détecte le BPM, coupe tes plans sur les temps, cale tes paroles à la milliseconde et exporte une vidéo 9:16 prête pour TikTok. Aucun logiciel à installer.",
    "hero.cta": "Commencer gratuitement",
    "hero.seePricing": "Voir les tarifs",
    "hero.note": "GRATUIT : STUDIO COMPLET AVEC WATERMARK • PRO : EXPORT SANS WATERMARK — 12,99 €/MOIS",
    "pricing.tag": "[ TARIFS ]",
    "pricing.title": "Simple. Sans engagement.",
    "pricing.note": "Désabonnement en 1 clic depuis ton compte, à tout moment.",
    "pricing.monthly": "MENSUEL",
    "pricing.yearly": "ANNUEL",
    "pricing.yearlyBadge": "2 mois offerts",
    "pricing.free": "GRATUIT",
    "pricing.freeNote": "/ pour toujours",
    "pricing.freeCta": "Commencer gratuitement",
    "pricing.proCta": "Passer en PRO",
    "pricing.proCtaYear": "Passer en PRO — 99 €/an",
    "pricing.recommended": "RECOMMANDÉ",
    "gallery.tag": "[ GALERIE ]",
    "gallery.title": "Ce que tu peux sortir aujourd'hui.",
    "gallery.note": "Vidéos exportées en moins de 60 secondes, prêtes pour TikTok.",
    "cta.final.tag": "PRÊT À POSTER ?",
    "cta.final.title1": "Ton prochain son mérite",
    "cta.final.title2": "une vraie vidéo.",
    "cta.final.btn": "Ouvrir le studio",
    "footer.note": "Le studio beat-sync dans ton navigateur. Des vidéos calées sur le beat, prêtes pour TikTok.",
  },
  en: {
    "nav.features": "Features",
    "nav.how": "How it works",
    "nav.pricing": "Pricing",
    "nav.login": "Sign in",
    "nav.register": "Start for free",
    "nav.account": "Account",
    "nav.openStudio": "Open studio",
    "nav.logout": "Sign out",
    "hero.tag": "BEAT-SYNC STUDIO — 100% IN YOUR BROWSER",
    "hero.title1": "Videos cut",
    "hero.title2": "to the beat.",
    "hero.title3": "In 60 seconds.",
    "hero.desc": "Drop your track, add your clips: BEATCUT detects the BPM, cuts your shots on every beat, syncs your lyrics to the millisecond and exports a 9:16 video ready for TikTok. No software needed.",
    "hero.cta": "Start for free",
    "hero.seePricing": "See pricing",
    "hero.note": "FREE : FULL STUDIO WITH WATERMARK • PRO : EXPORT WITHOUT WATERMARK — €12.99/MONTH",
    "pricing.tag": "[ PRICING ]",
    "pricing.title": "Simple. No commitment.",
    "pricing.note": "Cancel in 1 click from your account, anytime.",
    "pricing.monthly": "MONTHLY",
    "pricing.yearly": "YEARLY",
    "pricing.yearlyBadge": "2 months free",
    "pricing.free": "FREE",
    "pricing.freeNote": "/ forever",
    "pricing.freeCta": "Start for free",
    "pricing.proCta": "Go PRO",
    "pricing.proCtaYear": "Go PRO — €99/year",
    "pricing.recommended": "RECOMMENDED",
    "gallery.tag": "[ GALLERY ]",
    "gallery.title": "What you can ship today.",
    "gallery.note": "Exported in under 60 seconds, TikTok-ready.",
    "cta.final.tag": "READY TO POST?",
    "cta.final.title1": "Your next track deserves",
    "cta.final.title2": "a real video.",
    "cta.final.btn": "Open the studio",
    "footer.note": "Beat-sync studio right in your browser. Videos cut to the beat, ready for TikTok.",
  },
};

const I18nContext = createContext({ lang: "fr", t: (k) => k, setLang: () => {} });

export function I18nProvider({ children }) {
  const [lang, setLangState] = useState(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored === "fr" || stored === "en") return stored;
    } catch {
      /* ignore */
    }
    return "fr";   // FR par défaut — l'utilisateur bascule en EN via le toggle nav
  });
  useEffect(() => {
    try { localStorage.setItem(STORAGE_KEY, lang); } catch {}
    document.documentElement.lang = lang;
  }, [lang]);
  const t = (key) => T[lang][key] ?? T.fr[key] ?? key;
  const setLang = (l) => setLangState(l === "en" ? "en" : "fr");
  return <I18nContext.Provider value={{ lang, t, setLang }}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  return useContext(I18nContext);
}
