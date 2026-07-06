import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  AudioWaveform,
  Scissors,
  Sparkles,
  Type,
  Tv,
  Smartphone,
  Check,
  ArrowRight,
} from "lucide-react";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import { useAuth } from "@/context/AuthContext";

const fadeUp = {
  initial: { opacity: 0, y: 24 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-80px" },
  transition: { duration: 0.55, ease: "easeOut" },
};

const FEATURES = [
  {
    icon: AudioWaveform,
    title: "BPM détecté automatiquement",
    desc: "Dépose ton track : le tempo, l'offset et la waveform interactive sont calculés en quelques secondes. Bouton « Trouver le drop » inclus.",
  },
  {
    icon: Scissors,
    title: "Cuts calés sur le beat",
    desc: "Tes clips vidéo sont découpés et enchaînés exactement sur les temps. ½ temps, 1 temps, 2 temps, 4 temps — à toi de choisir l'intensité.",
  },
  {
    icon: Sparkles,
    title: "Paroles détectées par IA",
    desc: "Whisper transcrit et cale chaque mot à la milliseconde. Corrige le texte : les timings sont conservés. Synchro TAP et import .lrc/.srt aussi.",
  },
  {
    icon: Type,
    title: "8 styles de sous-titres animés",
    desc: "CAPS POP, karaoké, glitch, VHS terminal, néon, minimal… avec polices, couleurs, contours et animations réglables.",
  },
  {
    icon: Tv,
    title: "Effets VHS, glitch & flash",
    desc: "Grain, scanlines, timecode, glitch sur les cuts, zoom punch, shake. 6 templates 1-clic pour régler tout le style d'un coup.",
  },
  {
    icon: Smartphone,
    title: "Export 9:16 prêt pour TikTok",
    desc: "Export mp4 (H.264) directement depuis le navigateur, en 9:16, 1:1 ou 16:9. Sous-titres .srt réutilisables dans CapCut ou Premiere.",
  },
];

const STEPS = [
  { tag: "[01]", title: "Dépose ton son", desc: "mp3, wav ou m4a — le BPM et le drop sont détectés tout seuls." },
  { tag: "[02]", title: "Ajoute tes clips", desc: "Tes rushs ou la banque Pexels intégrée. L'auto-cut fait le reste." },
  { tag: "[03]", title: "Lance l'IA", desc: "Les paroles sont transcrites et calées mot par mot sur la musique." },
  { tag: "[04]", title: "Exporte", desc: "Vidéo mp4 verticale + fichier .srt, prêts à poster." },
];

export default function Landing() {
  const { user } = useAuth();
  const ctaTarget = user ? "/studio" : "/register";
  const proTarget = user ? "/dashboard?upgrade=1" : "/register";
  const proLink = (plan) => (user ? `/dashboard?upgrade=1&plan=${plan}` : "/register");

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Navbar landing />

      {/* ============ HERO ============ */}
      <section className="relative overflow-hidden">
        <div
          className="absolute inset-0 bg-cover bg-center opacity-25"
          style={{
            backgroundImage:
              "url(https://images.unsplash.com/photo-1765539160785-e7953620488f?crop=entropy&cs=srgb&fm=jpg&q=85&w=1800)",
          }}
        />
        <div className="absolute inset-0 bg-gradient-to-b from-background/70 via-background/85 to-background" />
        <div className="relative mx-auto max-w-4xl px-5 sm:px-8 pt-20 pb-24 sm:pt-28 sm:pb-32 text-center">
          <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7 }}>
            <p className="font-osd text-xs tracking-[0.25em] text-[#d9ffd0] mb-6 flex items-center justify-center gap-3">
              <span className="rec-dot" /> STUDIO BEAT-SYNC — 100% DANS TON NAVIGATEUR
            </p>
            <h1 className="font-display text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight leading-[1.05]">
              Des vidéos calées
              <br />
              sur le beat.
              <br />
              <span className="text-primary">En 60 secondes.</span>
            </h1>
            <p className="mt-6 text-base text-muted-foreground max-w-2xl mx-auto leading-relaxed">
              Dépose ton track, ajoute tes clips : BEATCUT détecte le BPM, coupe tes plans sur les temps,
              cale tes paroles à la milliseconde et exporte une vidéo 9:16 prête pour TikTok. Aucun logiciel à installer.
            </p>
            <div className="mt-9 flex flex-wrap items-center justify-center gap-4">
              <Link
                to={ctaTarget}
                data-testid="hero-cta-button"
                className="inline-flex items-center gap-2 bg-primary text-white font-bold px-7 py-3.5 hover:bg-[#d32f2f] transition-all hover:-translate-y-1 shadow-[0_0_25px_rgba(255,59,48,0.4)]"
              >
                Commencer gratuitement <ArrowRight size={17} />
              </Link>
              <a
                href="#tarifs"
                data-testid="hero-pricing-link"
                className="border border-border text-foreground px-7 py-3.5 hover:border-foreground transition-colors"
              >
                Voir les tarifs
              </a>
            </div>
            <p className="mt-5 font-osd text-xs text-muted-foreground">
              GRATUIT : STUDIO AVEC WATERMARK • BASIC : 10 VIDÉOS/MOIS — 6,99 € • PRO : ILLIMITÉ + ACAPELLA — 12,99 €/MOIS
            </p>
          </motion.div>
        </div>
      </section>

      {/* ============ BANDEAU MONO ============ */}
      <div className="border-y border-border bg-[#0d0b11] overflow-hidden py-3">
        <div className="marquee font-osd text-xs text-[#d9ffd0]/80 whitespace-nowrap">
          {Array(2)
            .fill("BPM AUTO • CUTS SUR LE BEAT • PAROLES IA • SOUS-TITRES ANIMÉS • EFFETS VHS • EXPORT MP4 9:16 • LOOP TIKTOK SANS COUTURE • ")
            .map((t, i) => (
              <span key={i}>{t}</span>
            ))}
        </div>
      </div>

      {/* ============ FONCTIONNALITÉS ============ */}
      <section id="fonctionnalites" className="mx-auto max-w-7xl px-5 sm:px-8 py-24 sm:py-32">
        <motion.div {...fadeUp} className="max-w-2xl mb-14">
          <p className="font-osd text-xs tracking-[0.25em] text-primary mb-4">[ FONCTIONNALITÉS ]</p>
          <h2 className="font-display text-3xl sm:text-4xl font-extrabold tracking-tight">
            Tout un studio de montage, sans le montage.
          </h2>
        </motion.div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {FEATURES.map((f, i) => (
            <motion.div
              key={f.title}
              {...fadeUp}
              transition={{ duration: 0.5, delay: i * 0.06 }}
              className="group bg-card border border-border p-8 hover:border-[#d9ffd0]/60 transition-colors"
              data-testid={`feature-card-${i}`}
            >
              <f.icon className="text-primary mb-5" size={26} strokeWidth={1.7} />
              <h3 className="font-display text-lg font-bold mb-2.5">{f.title}</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">{f.desc}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* ============ COMMENT ÇA MARCHE ============ */}
      <section id="comment" className="border-y border-border bg-[#0d0b11]">
        <div className="mx-auto max-w-7xl px-5 sm:px-8 py-24 sm:py-32">
          <motion.div {...fadeUp} className="max-w-2xl mb-14">
            <p className="font-osd text-xs tracking-[0.25em] text-primary mb-4">[ COMMENT ÇA MARCHE ]</p>
            <h2 className="font-display text-3xl sm:text-4xl font-extrabold tracking-tight">
              De ton track à TikTok en 4 étapes.
            </h2>
          </motion.div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-10">
            {STEPS.map((s, i) => (
              <motion.div key={s.tag} {...fadeUp} transition={{ duration: 0.5, delay: i * 0.08 }}>
                <p className="font-osd text-lg text-primary mb-3">{s.tag}</p>
                <h3 className="font-display text-lg font-bold mb-2">{s.title}</h3>
                <p className="text-sm text-muted-foreground leading-relaxed">{s.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ============ TARIFS ============ */}
      <section id="tarifs" className="mx-auto max-w-7xl px-5 sm:px-8 py-24 sm:py-32">
        <motion.div {...fadeUp} className="max-w-2xl mb-14">
          <p className="font-osd text-xs tracking-[0.25em] text-primary mb-4">[ TARIFS ]</p>
          <h2 className="font-display text-3xl sm:text-4xl font-extrabold tracking-tight">
            Simple. Sans engagement.
          </h2>
          <p className="mt-4 text-muted-foreground text-base">
            Désabonnement en 1 clic depuis ton compte, à tout moment.
          </p>
        </motion.div>

        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
          {/* Gratuit */}
          <motion.div {...fadeUp} className="bg-card border border-border p-8" data-testid="pricing-free-card">
            <p className="font-osd text-xs tracking-[0.2em] text-muted-foreground mb-3">GRATUIT</p>
            <p className="font-display text-3xl font-extrabold">
              0 € <span className="text-sm font-normal text-muted-foreground">/ pour toujours</span>
            </p>
            <ul className="mt-6 space-y-2.5 text-sm">
              {["Studio complet : BPM, cuts, IA, styles", "Aperçu illimité dans le navigateur", "Banque de clips Pexels intégrée", "Aperçu avec watermark BEATCUT"].map((f) => (
                <li key={f} className="flex items-start gap-2.5 text-muted-foreground">
                  <Check size={15} className="text-[#d9ffd0] mt-0.5 shrink-0" /> {f}
                </li>
              ))}
            </ul>
            <Link
              to={ctaTarget}
              data-testid="pricing-free-button"
              className="mt-8 block text-center border border-border px-5 py-3 text-sm hover:border-foreground transition-colors"
            >
              Commencer gratuitement
            </Link>
          </motion.div>

          {/* BASIC */}
          <motion.div
            {...fadeUp}
            transition={{ duration: 0.55, delay: 0.05 }}
            className="relative bg-card border border-[#8f9bff]/50 p-8"
            data-testid="pricing-basic-card"
          >
            <span className="absolute -top-3 left-8 bg-[#8f9bff] text-background font-osd text-[10px] tracking-[0.2em] px-3 py-1">
              NOUVEAU
            </span>
            <p className="font-osd text-xs tracking-[0.2em] text-[#8f9bff] mb-3">BASIC</p>
            <p className="font-display text-3xl font-extrabold">
              6,99 € <span className="text-sm font-normal text-muted-foreground">/ mois</span>
            </p>
            <ul className="mt-6 space-y-2.5 text-sm">
              {["Tout le plan gratuit", "Export mp4 sans watermark", "10 vidéos par mois", "Sous-titres .srt", "Sans engagement"].map((f) => (
                <li key={f} className="flex items-start gap-2.5">
                  <Check size={15} className="text-[#8f9bff] mt-0.5 shrink-0" /> {f}
                </li>
              ))}
            </ul>
            <p className="mt-3 text-xs text-muted-foreground">Sans extraction d'acapella</p>
            <Link
              to={proLink("basic")}
              data-testid="pricing-basic-button"
              className="mt-6 block text-center border border-[#8f9bff]/60 bg-[#8f9bff]/10 text-foreground font-bold px-5 py-3 text-sm hover:bg-[#8f9bff]/20 transition-all hover:-translate-y-0.5"
            >
              Passer en BASIC
            </Link>
          </motion.div>

          {/* PRO mensuel */}
          <motion.div
            {...fadeUp}
            transition={{ duration: 0.55, delay: 0.1 }}
            className="relative bg-card border border-primary p-8 shadow-[0_0_40px_rgba(255,59,48,0.15)]"
            data-testid="pricing-pro-card"
          >
            <span className="absolute -top-3 left-8 bg-primary text-white font-osd text-[10px] tracking-[0.2em] px-3 py-1">
              RECOMMANDÉ
            </span>
            <p className="font-osd text-xs tracking-[0.2em] text-primary mb-3">PRO</p>
            <p className="font-display text-3xl font-extrabold">
              12,99 € <span className="text-sm font-normal text-muted-foreground">/ mois</span>
            </p>
            <ul className="mt-6 space-y-2.5 text-sm">
              {["Tout le plan BASIC", "Vidéos illimitées", "Extraction d'acapella (IA)", "Paroles calées à la milliseconde", "Sans engagement"].map((f) => (
                <li key={f} className="flex items-start gap-2.5">
                  <Check size={15} className="text-primary mt-0.5 shrink-0" /> {f}
                </li>
              ))}
            </ul>
            <Link
              to={proTarget}
              data-testid="pricing-pro-button"
              className="mt-8 block text-center bg-primary text-white font-bold px-5 py-3 text-sm hover:bg-[#d32f2f] transition-all hover:-translate-y-0.5 shadow-[0_0_20px_rgba(255,59,48,0.35)]"
            >
              Passer en PRO
            </Link>
          </motion.div>

          {/* PRO annuel */}
          <motion.div
            {...fadeUp}
            transition={{ duration: 0.55, delay: 0.2 }}
            className="relative bg-card border border-[#d9ffd0]/40 p-8"
            data-testid="pricing-yearly-card"
          >
            <span className="absolute -top-3 left-8 bg-[#d9ffd0] text-background font-osd text-[10px] tracking-[0.2em] px-3 py-1">
              2 MOIS OFFERTS
            </span>
            <p className="font-osd text-xs tracking-[0.2em] text-[#d9ffd0] mb-3">PRO ANNUEL</p>
            <p className="font-display text-3xl font-extrabold">
              99 € <span className="text-sm font-normal text-muted-foreground">/ an</span>
            </p>
            <p className="mt-1 font-osd text-[11px] text-muted-foreground">soit 8,25 €/mois</p>
            <ul className="mt-6 space-y-2.5 text-sm">
              {["Tout le plan PRO mensuel", "Économise 56 € sur l'année", "Priorité sur les nouveautés"].map((f) => (
                <li key={f} className="flex items-start gap-2.5">
                  <Check size={15} className="text-[#d9ffd0] mt-0.5 shrink-0" /> {f}
                </li>
              ))}
            </ul>
            <Link
              to={proLink("yearly")}
              data-testid="pricing-yearly-button"
              className="mt-8 block text-center border border-[#d9ffd0]/50 bg-[#d9ffd0]/5 text-foreground font-bold px-5 py-3 text-sm hover:bg-[#d9ffd0]/10 transition-all hover:-translate-y-0.5"
            >
              Passer en PRO annuel
            </Link>
          </motion.div>
        </div>

        {/* ===== Tableau comparatif ===== */}
        <motion.div {...fadeUp} className="mt-16 overflow-x-auto" data-testid="pricing-comparison-table">
          <p className="font-osd text-xs tracking-[0.25em] text-primary mb-5">[ COMPARER LES PLANS ]</p>
          <table className="w-full min-w-[560px] border border-border text-sm">
            <thead>
              <tr className="bg-secondary/60">
                <th className="text-left font-display font-bold px-5 py-4 border-b border-border w-[40%]">Fonctionnalité</th>
                <th className="text-center font-osd text-xs tracking-[0.15em] px-4 py-4 border-b border-border text-muted-foreground">GRATUIT</th>
                <th className="text-center font-osd text-xs tracking-[0.15em] px-4 py-4 border-b border-border text-[#8f9bff]">BASIC<br /><span className="normal-case font-sans text-[11px]">6,99 €/mois</span></th>
                <th className="text-center font-osd text-xs tracking-[0.15em] px-4 py-4 border-b border-border text-primary">PRO<br /><span className="normal-case font-sans text-[11px]">12,99 €/mois</span></th>
              </tr>
            </thead>
            <tbody>
              {[
                ["Studio complet (BPM auto, cuts sur le beat, effets)", true, true, true],
                ["Détection des paroles par IA", true, true, true],
                ["Banque de clips Pexels intégrée", true, true, true],
                ["14 styles de sous-titres animés", true, true, true],
                ["Export mp4 sans watermark", false, true, true],
                ["Vidéos par mois", "Aperçu seul", "10 vidéos", "Illimité"],
                ["Sous-titres .srt téléchargeables", false, true, true],
                ["Extraction d'acapella (IA GPU)", false, false, true],
                ["Paroles calées sur la voix isolée", false, false, true],
              ].map(([label, free, basic, pro]) => {
                const cell = (v, color) =>
                  typeof v === "boolean" ? (
                    v ? <Check size={16} className={`inline ${color}`} /> : <span className="text-muted-foreground/50">—</span>
                  ) : (
                    <span className="text-xs">{v}</span>
                  );
                return (
                  <tr key={label} className="border-b border-border/60 hover:bg-secondary/30 transition-colors">
                    <td className="px-5 py-3.5 text-muted-foreground">{label}</td>
                    <td className="text-center px-4 py-3.5">{cell(free, "text-[#d9ffd0]")}</td>
                    <td className="text-center px-4 py-3.5">{cell(basic, "text-[#8f9bff]")}</td>
                    <td className="text-center px-4 py-3.5">{cell(pro, "text-primary")}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="mt-4 text-xs text-muted-foreground">
            Tous les plans sont sans engagement — désabonnement en 1 clic depuis ton compte. Paiement sécurisé par Stripe.
          </p>
        </motion.div>
      </section>

      {/* ============ GALERIE ============ */}
      <section className="border-y border-border bg-[#0d0b11]">
        <div className="mx-auto max-w-7xl px-5 sm:px-8 py-24 sm:py-32">
          <motion.div {...fadeUp} className="max-w-2xl mb-12">
            <p className="font-osd text-xs tracking-[0.25em] text-primary mb-4">[ GALERIE ]</p>
            <h2 className="font-display text-3xl sm:text-4xl font-extrabold tracking-tight">
              Ce que tu peux sortir aujourd'hui.
            </h2>
            <p className="mt-4 text-sm text-muted-foreground">Vidéos exportées en moins de 60 secondes, prêtes pour TikTok.</p>
          </motion.div>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-5">
            {[
              "https://videos.pexels.com/video-files/3045163/3045163-hd_1080_1920_30fps.mp4",
              "https://videos.pexels.com/video-files/4980296/4980296-hd_1080_1920_25fps.mp4",
              "https://videos.pexels.com/video-files/3209828/3209828-hd_1080_1920_25fps.mp4",
              "https://videos.pexels.com/video-files/5377684/5377684-hd_1080_1920_25fps.mp4",
            ].map((src, i) => (
              <motion.div
                key={src}
                {...fadeUp}
                transition={{ duration: 0.5, delay: i * 0.08 }}
                className="relative aspect-[9/16] bg-black border border-border overflow-hidden group"
                data-testid={`gallery-clip-${i}`}
              >
                <video
                  src={src}
                  autoPlay
                  muted
                  loop
                  playsInline
                  preload="metadata"
                  className="w-full h-full object-cover opacity-90 group-hover:opacity-100 transition-opacity"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-black/40 via-transparent to-transparent pointer-events-none" />
                <span className="absolute bottom-3 left-3 font-osd text-[10px] tracking-wider text-[#d9ffd0]">
                  EXPORT 9:16 • {130 + i * 4} BPM
                </span>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ============ CTA FINAL ============ */}
      <section className="border-t border-border bg-[#0d0b11]">
        <div className="mx-auto max-w-7xl px-5 sm:px-8 py-24 text-center">
          <motion.div {...fadeUp}>
            <p className="font-osd text-xs tracking-[0.25em] text-[#d9ffd0] mb-5">PRÊT À POSTER ?</p>
            <h2 className="font-display text-3xl sm:text-5xl font-extrabold tracking-tight">
              Ton prochain son mérite
              <br />
              une vraie vidéo.
            </h2>
            <Link
              to={ctaTarget}
              data-testid="final-cta-button"
              className="mt-9 inline-flex items-center gap-2 bg-primary text-white font-bold px-8 py-4 hover:bg-[#d32f2f] transition-all hover:-translate-y-1 shadow-[0_0_30px_rgba(255,59,48,0.4)]"
            >
              Ouvrir le studio <ArrowRight size={17} />
            </Link>
          </motion.div>
        </div>
      </section>

      <Footer />
    </div>
  );
}
