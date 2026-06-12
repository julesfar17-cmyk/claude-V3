import { Logo } from "@/components/Navbar";

export default function Footer() {
  return (
    <footer className="border-t border-border bg-[#0d0b11]">
      <div className="mx-auto max-w-7xl px-5 sm:px-8 py-12 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6">
        <div className="space-y-2">
          <Logo />
          <p className="text-sm text-muted-foreground max-w-xs">
            Le studio beat-sync dans ton navigateur. Des vidéos calées sur le beat, prêtes pour TikTok.
          </p>
        </div>
        <div className="font-osd text-xs text-muted-foreground space-y-1 sm:text-right">
          <p>BPM AUTO • CUTS • PAROLES IA • EXPORT 9:16</p>
          <p>© {new Date().getFullYear()} BEATCUT — 9,99 €/mois, sans engagement.</p>
        </div>
      </div>
    </footer>
  );
}
