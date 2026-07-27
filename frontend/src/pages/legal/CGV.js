import LegalLayout, { CONTACT_EMAIL, COMPANY_NAME } from "./LegalLayout";

export default function CGV() {
  return (
    <LegalLayout title="Conditions générales de vente" updated="août 2026" testid="cgv-page">
      <section>
        <h2>1. Éditeur du service</h2>
        <p>
          Le service BeatCut (beat-cut.com) est édité par la {COMPANY_NAME}.
          Contact : <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.
        </p>
      </section>
      <section>
        <h2>2. Objet</h2>
        <p>
          BeatCut est un studio vidéo en ligne qui transforme un morceau de musique en vidéos courtes calées sur le
          beat (détection du tempo, montage automatique, sous-titres). Les présentes CGV régissent toute souscription
          à un abonnement payant.
        </p>
      </section>
      <section>
        <h2>3. Offres et tarifs</h2>
        <ul>
          <li><b>Gratuit</b> — 1 export offert pour tester le service avec ton propre son.</li>
          <li><b>Basic — 6,99 €/mois</b> — 10 exports par mois, sans watermark, sous-titres .srt.</li>
          <li><b>Pro — 12,99 €/mois</b> — exports illimités, sans watermark, extraction d'acapella (IA).</li>
          <li><b>Pro Annuel — 99 €/an</b> — mêmes droits que Pro, facturé une fois par an (soit 8,25 €/mois).</li>
        </ul>
        <p>Les prix sont exprimés en euros, toutes taxes comprises. Ils peuvent évoluer ; le tarif en vigueur au moment de la souscription s'applique pour la période en cours.</p>
      </section>
      <section>
        <h2>4. Paiement</h2>
        <p>
          Le paiement s'effectue par carte bancaire via <b>Stripe</b>, prestataire de paiement sécurisé. Aucune donnée
          bancaire n'est stockée par BeatCut. L'abonnement est reconduit tacitement à chaque échéance (mensuelle ou
          annuelle) jusqu'à résiliation.
        </p>
      </section>
      <section>
        <h2>5. Droit de rétractation</h2>
        <p>
          BeatCut est un contenu numérique fourni immédiatement après paiement. Conformément à l'article L221-28 du
          Code de la consommation, en validant ta commande tu demandes l'exécution immédiate du service et renonces
          expressément à ton droit de rétractation de 14 jours. Un problème ? Écris-nous à{" "}
          <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a> : chaque demande est étudiée.
        </p>
      </section>
      <section>
        <h2>6. Résiliation</h2>
        <p>
          Tu peux résilier à tout moment en 2 clics depuis ton compte (« Se désabonner »). La résiliation prend effet
          à la fin de la période déjà payée : tu conserves tes droits jusqu'à cette date, puis ton compte repasse en
          formule gratuite. Aucun remboursement au prorata n'est effectué pour une période entamée.
        </p>
      </section>
      <section>
        <h2>7. Propriété des contenus</h2>
        <p>
          Les morceaux et clips que tu déposes restent ta propriété exclusive. Les vidéos exportées t'appartiennent
          entièrement, usage commercial compris : BeatCut ne revendique aucun droit sur ton contenu. Tu garantis
          disposer des droits nécessaires sur les fichiers que tu utilises.
        </p>
      </section>
      <section>
        <h2>8. Disponibilité et responsabilité</h2>
        <p>
          BeatCut est fourni « en l'état ». Nous mettons tout en œuvre pour assurer une disponibilité maximale, sans
          pouvoir garantir une continuité absolue (maintenance, incidents tiers). La responsabilité de l'éditeur est
          limitée au montant des sommes versées au cours des 12 derniers mois.
        </p>
      </section>
      <section>
        <h2>9. Droit applicable</h2>
        <p>
          Les présentes CGV sont soumises au droit français. En cas de litige, une solution amiable sera recherchée en
          priorité via <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.
        </p>
      </section>
    </LegalLayout>
  );
}
