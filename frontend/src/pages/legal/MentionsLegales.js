import LegalLayout, { CONTACT_EMAIL, COMPANY_NAME } from "./LegalLayout";

export default function MentionsLegales() {
  return (
    <LegalLayout title="Mentions légales" updated="août 2026" testid="mentions-page">
      <section>
        <h2>Éditeur</h2>
        <p>
          BeatCut (beat-cut.com) est édité par la {COMPANY_NAME}.<br />
          Directeur de la publication : Jules.<br />
          Contact : <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>
        </p>
      </section>
      <section>
        <h2>Hébergement</h2>
        <p>
          Application hébergée sur une infrastructure cloud sécurisée (Kubernetes) via la plateforme Emergent.
          Paiements opérés par Stripe Payments Europe Ltd, 1 Grand Canal Street Lower, Dublin, Irlande.
        </p>
      </section>
      <section>
        <h2>Propriété intellectuelle</h2>
        <p>
          La marque BeatCut, le design et le code du service sont protégés. Les contenus déposés par les utilisateurs
          (musiques, clips, vidéos exportées) restent leur propriété exclusive.
        </p>
      </section>
      <section>
        <h2>Signalement</h2>
        <p>
          Pour signaler un contenu ou un problème : <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.
        </p>
      </section>
    </LegalLayout>
  );
}
