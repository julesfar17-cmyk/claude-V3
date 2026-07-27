import { Mail, Clock, MessageCircle } from "lucide-react";
import LegalLayout, { CONTACT_EMAIL } from "./LegalLayout";

export default function Contact() {
  return (
    <LegalLayout title="Contact" testid="contact-page">
      <section>
        <p>
          Une question, un bug, une idée, un problème de paiement ? Écris directement — c'est un artiste indépendant
          qui te répond, pas un robot.
        </p>
      </section>
      <div className="border border-border bg-card rounded-2xl p-8 space-y-5">
        <div className="flex items-center gap-3">
          <Mail size={18} className="text-primary" />
          <a href={`mailto:${CONTACT_EMAIL}`} data-testid="contact-email-link" className="text-foreground font-bold text-base">
            {CONTACT_EMAIL}
          </a>
        </div>
        <div className="flex items-center gap-3 text-muted-foreground">
          <Clock size={18} className="text-primary" />
          <span>Réponse sous 48 h ouvrées, souvent bien plus vite.</span>
        </div>
        <div className="flex items-center gap-3 text-muted-foreground">
          <MessageCircle size={18} className="text-primary" />
          <span>Pense à joindre une capture d'écran et le navigateur utilisé si tu signales un bug.</span>
        </div>
        <a
          href={`mailto:${CONTACT_EMAIL}?subject=BeatCut%20—%20Contact`}
          data-testid="contact-cta-button"
          className="inline-flex items-center gap-2 bg-primary !text-white !no-underline font-bold px-6 py-3.5 hover:-translate-y-0.5 transition-transform"
        >
          <Mail size={16} /> Envoyer un email
        </a>
      </div>
    </LegalLayout>
  );
}
