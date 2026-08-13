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
        <h2>2. Objet et acceptation</h2>
        <p>
          BeatCut est un studio vidéo en ligne qui transforme un morceau de musique en vidéos courtes calées sur le
          beat (détection du tempo, montage automatique, sous-titres). Les présentes CGV régissent l'utilisation du
          service et toute souscription à un abonnement payant.
        </p>
        <p>
          L'acceptation des CGV est matérialisée par une case à cocher lors de la création du compte : elle vaut
          consentement exprès et ne peut être partielle. La date d'acceptation est horodatée et conservée. Sans
          acceptation, aucun compte ne peut être créé. Les CGV sont consultables à tout moment sur cette page.
        </p>
      </section>
      <section>
        <h2>3. Offres et tarifs</h2>
        <ul>
          <li><b>Essentiel — 9,99 €/mois</b> — 15 exports par mois, tous les styles et effets, banque de clips.</li>
          <li><b>Pro — 19,99 €/mois</b> — exports illimités, séries de vidéos, tous styles/effets/polices. <b>3 jours d'essai offerts</b> : la carte est enregistrée à la souscription, un email de rappel est envoyé avant la fin de l'essai, et l'abonnement démarre automatiquement à J+3 sauf annulation (possible à tout moment pendant l'essai, sans débit).</li>
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
          (tes morceaux et montages restent sauvegardés). Pendant l'essai de 3 jours, l'annulation est immédiate et
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
        <h2>9. Données personnelles</h2>
        <p>
          Les données personnelles sont traitées conformément au RGPD et à la loi Informatique et Libertés. Les
          modalités (finalités, durées de conservation, droits d'accès, de rectification, d'effacement et de
          portabilité) sont détaillées dans la <a href="/confidentialite">Politique de confidentialité</a>. Pour
          exercer tes droits : <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.
        </p>
      </section>
      <section>
        <h2>10. Modification des CGV</h2>
        <p>
          BeatCut peut faire évoluer les présentes CGV. En cas de modification substantielle (prix, droits, durée),
          les abonnés en cours sont informés par email au moins 30 jours avant l'entrée en vigueur et peuvent résilier
          sans frais avant cette date. La poursuite de l'utilisation du service après l'entrée en vigueur vaut
          acceptation des nouvelles conditions.
        </p>
      </section>
      <section>
        <h2>11. Médiation de la consommation</h2>
        <p>
          Conformément aux articles L611-1 et suivants du Code de la consommation, tout consommateur a le droit de
          recourir gratuitement à un médiateur de la consommation en vue de la résolution amiable d'un litige,
          après avoir d'abord adressé une réclamation écrite à{" "}
          <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a> restée sans réponse satisfaisante sous 60 jours.
          Tu peux également utiliser la plateforme européenne de règlement en ligne des litiges :{" "}
          <a href="https://ec.europa.eu/consumers/odr" target="_blank" rel="noopener noreferrer">
            ec.europa.eu/consumers/odr
          </a>.
        </p>
      </section>
      <section>
        <h2>12. Droit applicable et juridiction</h2>
        <p>
          Les présentes CGV sont soumises au droit français. En cas de litige, une solution amiable sera recherchée
          en priorité via <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>. À défaut, les tribunaux français
          seront compétents ; le consommateur peut saisir, à son choix, la juridiction de son lieu de résidence ou
          celle du siège de l'éditeur.
        </p>
      </section>
    </LegalLayout>
  );
}
