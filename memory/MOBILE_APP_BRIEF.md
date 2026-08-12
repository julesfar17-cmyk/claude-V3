# BRIEF — App mobile native BeatCut (Expo / React Native)

> À coller comme prompt de départ dans un NOUVEAU projet Emergent avec le **Mobile Agent**.

## Produit
BeatCut transforme un morceau de musique en vidéos courtes calées sur le beat (TikTok/Reels/Shorts) :
détection du BPM, montage automatique des clips sur les temps, sous-titres IA synchronisés à la voix,
styles/effets (polices, couleurs, VHS/glitch, karaoké, mots mis en avant), export MP4 9:16.
L'app mobile doit être un STUDIO NATIF COMPLET (pas une WebView), même parcours que le studio web mobile
(navigation par onglets bas : Son / Clips / Paroles / Style, timeline, export).

## Backend EXISTANT à réutiliser (ne rien recréer)
Base URL : https://beat-cut.com/api (FastAPI + MongoDB, déjà en production)
Auth : cookie de session (session_token) OU header Authorization Bearer — sessions uniques par compte
(1 seule session active, le 2e login déconnecte le 1er ; admin exempté).

Endpoints clés :
- POST /auth/register {name,email,password,cgv_accepted:true} · POST /auth/login · GET /auth/me · POST /auth/logout
- Google login : Emergent-managed auth (voir playbook Emergent Auth côté mobile)
- GET/POST /projects, GET /projects/{id}, PUT /projects/{id} (state JSON du montage, format v2 :
  {audioMediaId, clipRefs:[{mediaId,name,...}], cuts, words, style, ext, fx})
- POST /media (upload GridFS, chunké), GET /media/{id} (stream)
- POST /export/finalize (multipart video+audio → MP4 muxé serveur, ffmpeg -c:v copy)
- GET /export/quota (tiers : free=paywall, basic 10/mois, essentiel 15/mois, essai 15, pro/studio illimité)
- POST /payments/checkout {plan, origin_url} → URL Stripe Checkout (ouvrir en navigateur in-app)
- POST /payments/activate-now (fin d'essai immédiate) · POST /subscription/cancel · cancel-feedback
- POST /promo/apply {code} → accès PRO temporaire (promo_pro_until)
- GET /subscription (sub_info : tier/plan/status/trial/promo)
- Paroles IA : POST /lyrics/transcribe (Whisper) — vérifier le nom exact dans server.py
- Séparation voix : POST /separate (Replicate) — vérifier le nom exact dans server.py

## Spécificités techniques mobile (important)
- Le studio web utilise WebCodecs (inexistant en RN). Pour le natif :
  - Lecture/preview : expo-av / expo-video + overlay des sous-titres en composants RN (pas de canvas).
  - Analyse BPM : soit portage JS de la détection (le web la fait en JS sur PCM décodé), soit endpoint
    serveur à ajouter (POST /audio/analyze → bpm + beats[]). PRÉFÉRER le serveur sur mobile.
  - Export final : rendu côté SERVEUR recommandé (le backend a déjà ffmpeg + Mux) : envoyer le state
    du projet, le serveur assemble le MP4 (nouvel endpoint /export/render à créer côté backend web).
  - Vignettes : expo-video-thumbnails.
- Tous les prix : Essentiel 9,99 €/mois, Pro 19,99 €/mois (essai 7 j), Pro Annuel 149 €, Studio 499 €/an.
  ⚠️ Apple/Google : les achats d'abonnement in-app peuvent exiger IAP — pour commencer, ouvrir Stripe
  Checkout dans le navigateur externe et à terme prévoir RevenueCat/IAP.
- Langue : FR par défaut, EN supporté.
- Identité visuelle : fond sombre #0B0E13, cartes #151A21, accent rouge #FF453A, vert accent #d9ffd0,
  typo display type "Bricolage Grotesque"/Anton, style « studio d'enregistrement » (REC dot, osd font).

## Parcours à implémenter (v1)
1. Onboarding : questionnaire 5 questions + 3 écrans de stats motivantes (voir web), tuto 7 étapes.
2. Auth (email+mdp avec case CGV obligatoire, Google via Emergent Auth).
3. Accueil : liste des morceaux (projets), création.
4. Studio : Son (upload/bibliothèque, BPM auto, choix extrait) → Clips (upload multi + banque Pexels
   via backend) → Paroles (transcription IA, édition mot à mot, mots mis en avant par tap) → Style
   (presets, polices, couleurs, effets) → timeline (remplacer/découper/supprimer un plan) → Export.
5. Compte : abonnement/quota/essai (bannières identiques au web), code promo, annulation avec feedback.

## Comptes de test (preview web)
demo@beatcut.fr / Demo1234! (basic) — admin julesfar17@gmail.com (voir test_credentials.md)

## Contact
Éditeur : jules.beatcut@gmail.com — CGV : https://beat-cut.com/cgv
