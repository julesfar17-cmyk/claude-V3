import LegalLayout, { CONTACT_EMAIL, COMPANY_NAME } from "./LegalLayout";

export default function Confidentialite() {
  return (
    <LegalLayout title="Politique de confidentialité" updated="août 2026" testid="confidentialite-page">
      <section>
        <h2>1. Qui traite tes données ?</h2>
        <p>
          La {COMPANY_NAME}, éditrice de BeatCut (beat-cut.com). Contact :{" "}
          <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.
        </p>
      </section>
      <section>
        <h2>2. Données collectées</h2>
        <ul>
          <li><b>Compte</b> : adresse email, nom, mot de passe (haché, jamais stocké en clair) ou connexion Google.</li>
          <li><b>Projets</b> : morceaux, clips et réglages que tu enregistres, stockés pour te permettre de reprendre ton montage sur n'importe quel appareil.</li>
          <li><b>Paiement</b> : traité intégralement par Stripe — BeatCut ne voit ni ne stocke jamais ta carte bancaire.</li>
          <li><b>Technique</b> : journaux d'export et de compatibilité navigateur (anonymes ou liés au compte), utilisés uniquement pour corriger les bugs.</li>
        </ul>
      </section>
      <section>
        <h2>3. Ce que nous ne faisons PAS</h2>
        <p>
          Tes vidéos sont montées <b>dans ton navigateur</b> : tes clips ne transitent par nos serveurs que pour la
          sauvegarde de tes projets et l'optimisation vidéo. Aucune revente de données, aucune publicité ciblée,
          aucun partage avec des tiers en dehors des prestataires strictement nécessaires (Stripe pour le paiement,
          hébergement cloud, Mux pour l'optimisation vidéo).
        </p>
      </section>
      <section>
        <h2>4. Cookies</h2>
        <p>
          BeatCut utilise uniquement un cookie de session sécurisé (httpOnly) pour te maintenir connecté. Pas de
          cookies publicitaires, pas de traceurs tiers.
        </p>
      </section>
      <section>
        <h2>5. Durée de conservation</h2>
        <p>
          Tes données sont conservées tant que ton compte est actif. Les fichiers médias des projets inactifs peuvent
          être purgés après une longue période d'inactivité (ton projet reste rechargeable). Tu peux demander la
          suppression complète de ton compte à tout moment.
        </p>
      </section>
      <section>
        <h2>6. Tes droits (RGPD)</h2>
        <p>
          Conformément au RGPD, tu disposes d'un droit d'accès, de rectification, de suppression, de portabilité et
          d'opposition sur tes données. Pour l'exercer, écris à{" "}
          <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a> — réponse sous 30 jours maximum. Tu peux aussi saisir
          la CNIL (cnil.fr) si tu estimes que tes droits ne sont pas respectés.
        </p>
      </section>
    </LegalLayout>
  );
}
