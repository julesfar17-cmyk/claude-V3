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
          <li><b>Essentiel — 9,99 €/mois</b> — 15 exports par mois, tous les styles et effets, banque de clips.</li>
          <li><b>Pro — 19,99 €/mois</b> — exports illimités, séries de vidéos, tous styles/effets/polices. <b>7 jours d'essai offerts</b> : la carte est enregistrée à la souscription, un email de rappel est envoyé avant la fin de l'essai, et l'abonnement démarre automatiquement à J+7 sauf annulation (possible à tout moment pendant l'essai, sans débit).</li>
          <li><b>Pro Annuel — 149 €/an</b> — mêmes droits que Pro, facturé une fois par an (soit 12,42 €/mois).</li>
          <li><b>Studio — 499 €/an</b> — 5 profils artistes séparés, 3 utilisateurs, watermark personnalisé, onboarding individuel et support prioritaire. Facturé une fois par an.</li>
        </ul>
        <p>Les prix sont exprimés en euros, toutes taxes comprises. Ils peuvent évoluer ; le tarif en vigueur au moment de la souscription s'applique pour la période en cours. Les abonnés ayant souscrit une ancienne formule conservent leur prix et leurs conditions.</p>
        <p><b>Compte individuel.</b> Le compte BeatCut est strictement personnel : une seule session active à la fois (plans Essentiel et Pro). L'usage multi-utilisateurs (3 sessions simultanées, 5 profils artistes) est réservé au plan Studio.</p>
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
          à la fin de la période déjà payée : tu conserves tes droits jusqu'à cette date, puis l'export est verrouillé
          (tes morceaux et montages restent sauvegardés). Pendant l'essai de 7 jours, l'annulation est immédiate et
          rien n'est débité. Aucun remboursement au prorata n'est effectué pour une période entamée.
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
