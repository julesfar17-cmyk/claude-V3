import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { Check, ArrowRight } from "lucide-react";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import { useAuth } from "@/context/AuthContext";

const fadeUp = {
  initial: { opacity: 0, y: 24 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-80px" },
  transition: { duration: 0.55, ease: "easeOut" },
};

const STEPS = [
  { n: "1", title: "Dépose ton son", desc: "Le tempo et le drop sont détectés tout seuls." },
  { n: "2", title: "Ajoute tes paroles", desc: "L'IA les cale sur ta voix, mot par mot. Ou colle ton texte officiel." },
  { n: "3", title: "Choisis un style", desc: "Plans calés sur le beat, sous-titres animés, effets." },
  { n: "4", title: "Exporte et poste", desc: "mp4 vertical prêt pour TikTok, Reels et Shorts." },
];

function Waveform() {
  return (
    <div className="flex items-end gap-[3px] h-24" aria-hidden>
      {Array.from({ length: 34 }).map((_, i) => (
        <span
          key={i}
          className="w-[5px] rounded-sm bg-primary animate-pulse"
          style={{
            height: `${18 + Math.abs(Math.sin(i * 1.7)) * 78}%`,
            animationDelay: `${(i % 7) * 0.12}s`,
            opacity: 0.55 + Math.abs(Math.sin(i * 2.3)) * 0.45,
          }}
        />
      ))}
    </div>
  );
}

export default function Landing() {
  const { user } = useAuth();
  const ctaTarget = user ? "/studio" : "/register";
  const proLink = (plan) => (user ? `/dashboard?upgrade=1&plan=${plan}` : "/register");

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Navbar />

      {/* ===== Hero ===== */}
      <section className="mx-auto max-w-5xl px-5 sm:px-8 pt-16 sm:pt-24 pb-16">
        <div className="bg-card border border-border rounded-2xl p-8 sm:p-14 grid md:grid-cols-[1.2fr_0.8fr] gap-10 items-center">
          <motion.div {...fadeUp}>
            <h1 className="font-display text-4xl sm:text-5xl lg:text-6xl font-extrabold leading-[1.04] tracking-tight">
              Ton son.
              <br />
              Un mois de <span className="text-primary">vidéos</span>.
            </h1>
            <p className="mt-5 text-muted-foreground max-w-md leading-relaxed">
              Dépose ton morceau une fois : BeatCut trouve le tempo, cale les plans sur le beat et écrit
              tes paroles à l'écran. Ensuite, tu crées des vidéos à volonté.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-4">
              <Link
                to={ctaTarget}
                data-testid="hero-cta"
                className="inline-flex items-center gap-2 bg-primary text-white font-bold px-6 py-3.5 rounded-xl hover:brightness-110 transition-all hover:-translate-y-0.5 shadow-[0_0_24px_rgba(255,69,58,0.35)]"
              >
                + Créer une vidéo
              </Link>
              <a href="#tarifs" className="text-sm text-muted-foreground hover:text-foreground transition-colors inline-flex items-center gap-1.5">
                Voir les tarifs <ArrowRight size={14} />
              </a>
            </div>
            <p className="mt-5 font-osd text-[11px] tracking-wider text-muted-foreground">
              GRATUIT : 1 EXPORT DÉCOUVERTE SANS WATERMARK · SANS CARTE BANCAIRE
            </p>
          </motion.div>
          <motion.div {...fadeUp} transition={{ duration: 0.55, delay: 0.15 }} className="hidden md:flex justify-center">
            <Waveform />
          </motion.div>
        </div>
      </section>

      {/* ===== 4 étapes ===== */}
      <section className="mx-auto max-w-5xl px-5 sm:px-8 pb-20">
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {STEPS.map((s, i) => (
            <motion.div
              key={s.n}
              {...fadeUp}
              transition={{ duration: 0.5, delay: i * 0.08 }}
              className="bg-card border border-border rounded-xl p-6"
            >
              <span className="font-osd text-xs text-primary">{s.n}</span>
              <h3 className="font-display font-bold mt-2">{s.title}</h3>
              <p className="text-sm text-muted-foreground mt-1.5 leading-relaxed">{s.desc}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* ===== Tarifs ===== */}
      <section id="tarifs" className="mx-auto max-w-5xl px-5 sm:px-8 pb-20">
        <motion.div {...fadeUp}>
          <p className="font-osd text-xs tracking-[0.25em] text-primary mb-3">[ TARIFS ]</p>
          <h2 className="font-display text-2xl sm:text-3xl font-extrabold mb-10">
            Simple. Sans engagement.
          </h2>
        </motion.div>
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Gratuit */}
          <motion.div {...fadeUp} className="bg-card border border-border rounded-xl p-7" data-testid="pricing-free-card">
            <p className="font-osd text-xs tracking-[0.2em] text-muted-foreground mb-2">GRATUIT</p>
            <p className="font-display text-3xl font-extrabold">0 €</p>
            <ul className="mt-5 space-y-2 text-sm text-muted-foreground">
              {["Studio complet", "1 export découverte sans watermark", "Banque de clips intégrée"].map((f) => (
                <li key={f} className="flex items-start gap-2"><Check size={14} className="text-emerald-400 mt-0.5 shrink-0" />{f}</li>
              ))}
            </ul>
            <Link to={ctaTarget} data-testid="pricing-free-button" className="mt-7 block text-center border border-border rounded-lg px-4 py-2.5 text-sm hover:border-foreground transition-colors">
              Commencer
            </Link>
          </motion.div>
          {/* Basic */}
          <motion.div {...fadeUp} transition={{ duration: 0.5, delay: 0.05 }} className="relative bg-card border border-sky-400/40 rounded-xl p-7" data-testid="pricing-basic-card">
            <span className="absolute -top-2.5 left-6 bg-sky-400 text-background font-osd text-[10px] tracking-[0.2em] px-2.5 py-0.5 rounded">NOUVEAU</span>
            <p className="font-osd text-xs tracking-[0.2em] text-sky-400 mb-2">BASIC</p>
            <p className="font-display text-3xl font-extrabold">6,99 € <span className="text-sm font-normal text-muted-foreground">/mois</span></p>
            <ul className="mt-5 space-y-2 text-sm text-muted-foreground">
              {["10 vidéos par mois", "Sans watermark", "Sous-titres .srt", "10 projets sauvegardés"].map((f) => (
                <li key={f} className="flex items-start gap-2"><Check size={14} className="text-sky-400 mt-0.5 shrink-0" />{f}</li>
              ))}
            </ul>
            <Link to={proLink("basic")} data-testid="pricing-basic-button" className="mt-7 block text-center border border-sky-400/50 bg-sky-400/10 rounded-lg px-4 py-2.5 text-sm font-bold hover:bg-sky-400/20 transition-colors">
              Passer en BASIC
            </Link>
          </motion.div>
          {/* Pro */}
          <motion.div {...fadeUp} transition={{ duration: 0.5, delay: 0.1 }} className="relative bg-card border border-primary rounded-xl p-7 shadow-[0_0_32px_rgba(255,69,58,0.15)]" data-testid="pricing-pro-card">
            <span className="absolute -top-2.5 left-6 bg-primary text-white font-osd text-[10px] tracking-[0.2em] px-2.5 py-0.5 rounded">RECOMMANDÉ</span>
            <p className="font-osd text-xs tracking-[0.2em] text-primary mb-2">PRO</p>
            <p className="font-display text-3xl font-extrabold">12,99 € <span className="text-sm font-normal text-muted-foreground">/mois</span></p>
            <ul className="mt-5 space-y-2 text-sm text-muted-foreground">
              {["Vidéos illimitées", "Extraction d'acapella (IA)", "Paroles calées sur la voix isolée", "Projets illimités"].map((f) => (
                <li key={f} className="flex items-start gap-2"><Check size={14} className="text-primary mt-0.5 shrink-0" />{f}</li>
              ))}
            </ul>
            <Link to={proLink("monthly")} data-testid="pricing-pro-button" className="mt-7 block text-center bg-primary text-white rounded-lg px-4 py-2.5 text-sm font-bold hover:brightness-110 transition-all shadow-[0_0_18px_rgba(255,69,58,0.35)]">
              Passer en PRO
            </Link>
          </motion.div>
          {/* Annuel */}
          <motion.div {...fadeUp} transition={{ duration: 0.5, delay: 0.15 }} className="relative bg-card border border-emerald-400/40 rounded-xl p-7" data-testid="pricing-yearly-card">
            <span className="absolute -top-2.5 left-6 bg-emerald-400 text-background font-osd text-[10px] tracking-[0.2em] px-2.5 py-0.5 rounded">2 MOIS OFFERTS</span>
            <p className="font-osd text-xs tracking-[0.2em] text-emerald-400 mb-2">PRO ANNUEL</p>
            <p className="font-display text-3xl font-extrabold">99 € <span className="text-sm font-normal text-muted-foreground">/an</span></p>
            <p className="font-osd text-[11px] text-muted-foreground mt-1">soit 8,25 €/mois</p>
            <ul className="mt-5 space-y-2 text-sm text-muted-foreground">
              {["Tout le plan PRO", "Économise 56 €/an"].map((f) => (
                <li key={f} className="flex items-start gap-2"><Check size={14} className="text-emerald-400 mt-0.5 shrink-0" />{f}</li>
              ))}
            </ul>
            <Link to={proLink("yearly")} data-testid="pricing-yearly-button" className="mt-7 block text-center border border-emerald-400/50 bg-emerald-400/10 rounded-lg px-4 py-2.5 text-sm font-bold hover:bg-emerald-400/20 transition-colors">
              PRO annuel
            </Link>
          </motion.div>
        </div>

        {/* Tableau comparatif compact */}
        <motion.div {...fadeUp} className="mt-12 overflow-x-auto" data-testid="pricing-comparison-table">
          <table className="w-full min-w-[520px] border border-border rounded-xl text-sm">
            <thead>
              <tr className="bg-secondary/60">
                <th className="text-left font-display font-bold px-4 py-3 border-b border-border w-[42%]">Fonctionnalité</th>
                <th className="text-center font-osd text-[11px] tracking-wider px-3 py-3 border-b border-border text-muted-foreground">GRATUIT</th>
                <th className="text-center font-osd text-[11px] tracking-wider px-3 py-3 border-b border-border text-sky-400">BASIC</th>
                <th className="text-center font-osd text-[11px] tracking-wider px-3 py-3 border-b border-border text-primary">PRO</th>
              </tr>
            </thead>
            <tbody>
              {[
                ["Studio complet (tempo auto, plans sur le beat)", true, true, true],
                ["Paroles calées par IA", true, true, true],
                ["Vidéos", "1 découverte", "10 / mois", "Illimité"],
                ["Watermark", "Non (1er export)", "Non", "Non"],
                ["Extraction d'acapella (IA GPU)", false, false, true],
                ["Projets sauvegardés (cross-device)", "1", "10", "Illimité"],
                ["Stockage de tes médias", "200 Mo", "2 Go", "10 Go"],
              ].map(([label, free, basic, pro]) => {
                const cell = (v, color) =>
                  typeof v === "boolean" ? (
                    v ? <Check size={15} className={`inline ${color}`} /> : <span className="text-muted-foreground/50">—</span>
                  ) : (
                    <span className="text-xs">{v}</span>
                  );
                return (
                  <tr key={label} className="border-b border-border/60 hover:bg-secondary/30 transition-colors">
                    <td className="px-4 py-3 text-muted-foreground">{label}</td>
                    <td className="text-center px-3 py-3">{cell(free, "text-emerald-400")}</td>
                    <td className="text-center px-3 py-3">{cell(basic, "text-sky-400")}</td>
                    <td className="text-center px-3 py-3">{cell(pro, "text-primary")}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="mt-3 text-xs text-muted-foreground">
            Sans engagement — désabonnement en 1 clic. Paiement sécurisé par Stripe. Tes morceaux sont sauvegardés
            en ligne : retrouve-les sur n'importe quel appareil.
          </p>
        </motion.div>
      </section>

      {/* ===== CTA final ===== */}
      <section className="mx-auto max-w-5xl px-5 sm:px-8 pb-24">
        <motion.div {...fadeUp} className="bg-card border border-border rounded-2xl p-10 sm:p-14 text-center">
          <h2 className="font-display text-2xl sm:text-3xl font-extrabold">
            Ta prochaine vidéo est déjà <span className="text-primary">dans ton son</span>.
          </h2>
          <Link
            to={ctaTarget}
            data-testid="footer-cta"
            className="mt-7 inline-flex items-center gap-2 bg-primary text-white font-bold px-7 py-3.5 rounded-xl hover:brightness-110 transition-all hover:-translate-y-0.5 shadow-[0_0_24px_rgba(255,69,58,0.35)]"
          >
            Commencer gratuitement <ArrowRight size={16} />
          </Link>
        </motion.div>
      </section>

      <Footer />
    </div>
  );
}
