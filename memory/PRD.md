# PRD — BEATCUT

## Problème original
"Voici mon site en version html copie le et fais en un vrai site fonctionnel qui a une belle page d'accueil un système pour se désabonner une DA plus pro et propre et faire en sorte qu'il soit fonctionnel sur mobile et sur pc."
Fichier fourni : `beatcut.html` — studio de montage beat-sync 100% client-side (BPM auto, cuts sur le beat, paroles IA Whisper, 8 styles de sous-titres, effets VHS/glitch, export mp4 9:16).

## Choix utilisateur
- Auth : email/mot de passe (JWT) ET Google (Emergent-managed) — les deux
- Paiement : Stripe mode test (sk_test_emergent), abonnement PRO 9,99 €/mois + bouton "Se désabonner"
- Studio : conservé intégralement, intégré au nouveau site
- DA : garder les couleurs (noir #121016 / ivoire #ece6da / rouge #ff3b30 / vert OSD #d9ffd0) mais plus propre et moderne

## Architecture
- **Backend** FastAPI + MongoDB (`/app/backend/server.py`) : auth JWT (cookies httpOnly) + sessions Google Emergent, Stripe via emergentintegrations, collections `users`, `user_sessions`, `login_attempts`, `payment_transactions`
- **Frontend** React + Tailwind + shadcn (`/app/frontend/src`) : Landing, AuthPage (login/register), Dashboard (abonnement + désabonnement), Studio (iframe)
- **Studio** : `/app/frontend/public/studio.html` — l'app originale adaptée (Supabase retiré, auth via `/api/auth/me`, watermark gratuit conservé, bouton PRO → /dashboard?upgrade=1)
- Fonts : Cabinet Grotesk (display), DM Sans (body), JetBrains Mono (OSD)

## Modèle d'abonnement
- Paiement Stripe test → 30 jours PRO (`subscription.status=active`)
- "Se désabonner" → `status=canceled`, accès PRO conservé jusqu'à `current_period_end`, puis retour gratuit
- Prix fixé côté serveur uniquement (9,99 € EUR)

## Implémenté (12 juin 2026)
- ✅ Landing page FR responsive (hero, marquee, 6 features, 4 étapes, tarifs Gratuit/PRO, CTA, footer)
- ✅ Auth complète : register/login email+mdp, Google OAuth (Emergent), logout, routes protégées, brute force (5 essais/15 min, X-Forwarded-For)
- ✅ Stripe checkout PRO 9,99 €/mois + polling statut + webhook + transactions idempotentes
- ✅ Dashboard : badge plan, Passer en PRO, Se désabonner (AlertDialog), Se réabonner, infos compte
- ✅ Studio intégral intégré (iframe), watermark gratuit / export PRO, lien retour compte
- ✅ Tests E2E : backend 16/17 (1 env-only, corrigé), frontend 100%

## Comptes seedés
Voir `/app/memory/test_credentials.md` (admin@beatcut.fr, demo@beatcut.fr)

## Backlog priorisé
- **P1** : Renouvellement automatique réel (Stripe subscriptions natives au lieu de 30 jours par paiement) ; emails transactionnels (confirmation, fin d'abonnement)
- **P1** : Mot de passe oublié (reset par email)
- **P2** : Proxy serveur pour clés Groq/Pexels (l'utilisateur n'a plus à coller ses clés) — nécessite clés API
- **P2** : Historique des paiements dans le dashboard ; page admin
- **P2** : Galerie de vidéos exportées (object storage)

## Notes
- Les clés Groq (transcription cloud) et Pexels (banque de clips) restent côté navigateur de l'utilisateur (mode libre du studio d'origine)
- Stripe en MODE TEST (sk_test_emergent) — passer une vraie clé pour la prod
