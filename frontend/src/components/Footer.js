import { Link } from "react-router-dom";
import { Logo } from "@/components/Navbar";

export default function Footer() {
  return (
    <footer className="border-t border-border bg-[#0B0E13]">
      <div className="mx-auto max-w-7xl px-5 sm:px-8 py-12 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6">
        <div className="space-y-2">
          <Logo />
          <p className="text-sm text-muted-foreground max-w-xs">
            Le studio beat-sync dans ton navigateur. Des vidéos calées sur le beat, prêtes pour TikTok.
          </p>
          <p className="text-xs text-muted-foreground flex flex-wrap gap-x-3 gap-y-1 pt-1">
            <Link to="/cgv" data-testid="footer-cgv-link" className="underline underline-offset-4 hover:text-foreground">CGV</Link>
            <Link to="/confidentialite" data-testid="footer-privacy-link" className="underline underline-offset-4 hover:text-foreground">Confidentialité</Link>
            <Link to="/mentions-legales" data-testid="footer-mentions-link" className="underline underline-offset-4 hover:text-foreground">Mentions légales</Link>
            <Link to="/contact" data-testid="footer-contact-link" className="underline underline-offset-4 hover:text-foreground">Contact</Link>
          </p>
        </div>
        <div className="font-osd text-xs text-muted-foreground space-y-1 sm:text-right">
          <p>BPM AUTO • CUTS • PAROLES IA • EXPORT 9:16</p>
          <p>© {new Date().getFullYear()} BEATCUT — sans engagement, annulable en 2 clics.</p>
        </div>
      </div>
    </footer>
  );
}
