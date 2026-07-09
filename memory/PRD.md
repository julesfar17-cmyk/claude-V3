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
- Stripe RÉEL (clé sk_live du client) : checkout en mode `subscription` 12,99 €/mois récurrent
- Renouvellement automatique géré par Stripe ; synchronisé par polling (`sync_stripe_subscription` sur /auth/me)
- "Se désabonner" → `cancel_at_period_end=True` côté Stripe, accès conservé jusqu'à fin de période
- "Se réabonner" → réactivation Stripe si encore en période, sinon nouveau checkout

## Séparation voix/instru (acapella)
- **Replicate** + modèle **Demucs v4 (htdemucs)** via `cjwbw/demucs` — GPU à la demande, pay-per-use (~0,01-0,02 € par séparation)
- Scale-to-zero : aucun coût quand personne ne sépare
- Endpoint asynchrone : POST /api/separate → job_id, GET /api/separate/{id} statut, GET /api/separate/{id}/result wav
- Réservé aux abonnés PRO (403 sinon)

## Implémenté (12 juin 2026)
- ✅ Landing page FR responsive (hero, marquee, 6 features, 4 étapes, tarifs Gratuit/PRO, CTA, footer)
- ✅ Auth complète : register/login email+mdp, Google OAuth (Emergent), logout, routes protégées, brute force (X-Forwarded-For)
- ✅ Mot de passe oublié : /forgot-password + /reset-password (token 1h, usage unique) — emails simulés tant que RESEND_API_KEY vide (lien affiché à l'écran)
- ✅ Stripe LIVE récurrent : checkout subscription, annulation réelle, réactivation, sync renouvellement, transactions idempotentes
- ✅ Emails transactionnels (structure Resend prête : reset, confirmation PRO, confirmation annulation) — mode simulé en attendant le domaine
- ✅ Proxy clé-en-main : /api/proxy/pexels + /api/proxy/transcribe (clés Pexels/Groq côté serveur, champs masqués dans le studio)
- ✅ Dashboard : badge plan, Passer en PRO, Se désabonner (AlertDialog), Se réabonner, infos compte
- ✅ Studio intégral intégré (iframe), watermark gratuit / export PRO, lien retour compte
- ✅ Tests E2E itération 2 : backend 24/24, frontend 100%

## Implémenté (24 juin 2026)
- ✅ **6 nouveaux presets de sous-titres dynamiques** dans le Studio :
  - **TIKTOK NEON** : mot par mot, couleurs arc-en-ciel pulsantes + halo néon
  - **WORD POP 3D** : ombre stack 3D extrudée + rotation + scale sur le beat
  - **HANDWRITE** : écriture manuscrite révélée gauche-droite + trait fluo sous le mot
  - **BOUNCE RAINBOW** : chaque mot rebondit dans une couleur différente
  - **CINÉMA** : barres noires + sous-titre épuré centré (look pro/film)
  - **BIG IMPACT** : un mot massif occupe tout, drop shadow brutal, tilt et couleurs variables
- ✅ **9 nouvelles polices** ajoutées au dropdown (Anton, Bangers, Bungee, Righteous, Fredoka, Luckiest Guy, Permanent Marker, Rubik Mono One, Press Start 2P)
- ✅ **Texte derrière le sujet (IA)** : MediaPipe Selfie Segmentation chargé à la demande, masque la silhouette de la personne et réinjecte au-dessus du texte → le sous-titre passe DERRIÈRE le sujet
- ✅ Toggle "Derrière le sujet" dans la section Sous-titres, chargement lazy de l'IA au premier clic

## Corrections (juillet 2026)
- ✅ **Upload MP3 mobile (iOS Safari)** : suppression de l'attribut `accept` sur audioInput/clipInput/acapInput — iOS grisait les MP3 de l'app Fichiers. Validation 100% JS avec message d'erreur clair.
- ✅ **Séparation acapella cassée en PRODUCTION** : les jobs étaient stockés dans `SEP_JOBS` (dict en mémoire) → en prod multi-workers, le GET statut tombait sur un autre worker → "Job introuvable". Fix : jobs stockés dans MongoDB (`separation_jobs`), résultat streamé depuis l'URL Replicate via StreamingResponse. Testé E2E sur preview (job done en ~12s, WAV 529 Ko téléchargé).
- ⚠️ Ces correctifs nécessitent un REDÉPLOIEMENT pour être actifs sur beat-cut.com

## Implémenté (6 juillet 2026) — Plan BASIC 6,99 €
- ✅ **Nouveau plan BASIC** : 6,99 €/mois — export sans watermark, 10 vidéos/mois, sous-titres .srt, SANS acapella
- ✅ Backend : `sub_info` renvoie `tier` (free/basic/pro), checkout Stripe plan basic (699 cents), quota mensuel via `export_logs` MongoDB (`POST /api/export/register` → 429 au-delà de 10, `GET /api/export/quota`), acapella verrouillée PRO only (403 pour Basic), annulation auto de l'ancien abonnement Stripe en cas d'upgrade Basic→PRO, MRR admin inclut les basic
- ✅ Studio : export compté pour Basic (message "Export X/10 ce mois-ci"), overlay upgrade si quota atteint, acapella bloquée pour Basic (requireProPlan), auto-extraction acapella réservée tier pro
- ✅ Landing : 4 cartes tarifs (Gratuit / BASIC "NOUVEAU" / PRO "RECOMMANDÉ" / PRO Annuel) + **tableau comparatif** 9 fonctionnalités × 3 plans
- ✅ Dashboard : badge BASIC, barre de progression quota X/10, bouton "Passer en PRO" (remplace l'abonnement Basic), 3 boutons d'offres pour les comptes gratuits
- ✅ Tests : 17/17 backend (pytest `/app/backend/tests/test_basic_plan.py`), frontend 100% (iteration_3.json)
- ⚠️ Nécessite un REDÉPLOIEMENT pour beat-cut.com
- ℹ️ Compte demo@beatcut.fr configuré en plan Basic (test)

## Implémenté (7 juillet 2026) — Admin enrichi
- ✅ **MRR hors promos** : seuls les abonnés avec un vrai `stripe_subscription_id` actif comptent dans le MRR (les accès offerts via code promo sont exclus)
- ✅ **Compteur "Payants réels (Stripe)"** vs "Actifs via promo / offert" dans les stats admin
- ✅ **Liste complète de tous les inscrits** (`GET /api/admin/users`) : email, plan (badge coloré), payant ✓/offert, code promo utilisé, provider, date — table scrollable
- ✅ Bouton **"Copier tous les emails"** (presse-papier, pour newsletters)
- ✅ Nettoyage : 35 comptes de test résiduels supprimés de la DB preview
- ⚠️ Nécessite un REDÉPLOIEMENT pour beat-cut.com

## Implémenté (9 juillet 2026) — V2 COMPLÈTE (fichier fourni par Jules) — testé 100% (iteration_6)
### Studio V2 (`/app/frontend/public/studio.html`, ancien sauvegardé en studio-v1-backup.html)
- ✅ Nouvelle DA « encre bleutée + LED rouge » (Bricolage Grotesque/Inter/JetBrains Mono), SPA hash-routing (#/accueil, #/morceaux, #/edit/{id})
- ✅ **Toutes les APIs branchées** : auth réelle (/api/auth/me, avatar→/dashboard, redirect /login), plan+quota serveur, transcription Groq (/api/proxy/transcribe), acapella Replicate PRO (/api/separate), banque Pexels (UI de recherche ajoutée), upload/download GridFS
- ✅ **Morceaux cross-device** : store localStorage remplacé par /api/projects (bootRemote, persistRemote débounce 800ms, loadRemoteMorceau restaure audio GridFS + clips + paroles + style + extrait + BPM), suppression serveur avec bouton ✕
- ✅ Paroles : détection réelle (acapella si PRO → transcribe), « Coller mes paroles » avec remap LCS (remapPasted), « Recaler » réel
- ✅ Export : quota serveur vérifié AVANT, décompte APRÈS succès réel (/api/export/register)
- ✅ Garde beforeunload pendant l'upload audio ; window.API exposé pour les tests
### Nouvelle règle de quota export
- ✅ **GRATUIT = 1 export découverte AU TOTAL (lifetime), SANS watermark** (CDC §1) ; Basic = 10/mois ; Pro = illimité. Backend /api/export/register + /api/export/quota mis à jour (tests pytest adaptés)
### Landing + Profil nouvelle DA
- ✅ index.css : tokens globaux V2 (fond #0E1116, panel #151A21, accent #FF453A, radius 12px) → TOUTES les pages React héritent (Dashboard, Admin, Auth, Projects)
- ✅ Landing réécrite « simple » : hero waveform LED, 4 étapes, 4 cartes tarifs, tableau comparatif compact, CTA final
### Dette technique (iteration_6)
- Extraire js/{api,store,audio,subs}.js de studio.html ; data-testid manquants dans le studio V2 ; AbortController polling acapella ; retry persistRemote hors-ligne ; filtre mots fantômes transcription
- ⚠️ Nécessite un REDÉPLOIEMENT pour beat-cut.com
- ℹ️ NOTE : le phasage CDC (P1 Express, P3 styles/créateur, LOT 5) est en partie couvert par la V2 de Jules (pages, éditeur, presets, créateur de style local). Les quotas journaliers du CDC §1 (détections IA/jour, recherches clips/jour, acapella 20/j) restent À FAIRE côté serveur.

## Cahier des charges V2 (reçu 8 juillet 2026) — décisions de Jules
- Export découverte Gratuit (1 au total) : SANS watermark
- Stockage complet des médias pour les projets (LOT 4) : OUI dès l'implémentation
- Phasage : LOT 0 (bug synchro) ✅ → P2 (LOT 4 Projets ✅ puis LOT 2 Timeline ✅) → P1 (quotas + Express) → P3 (Styles + créateur) → LOT 5 transverse

## Implémenté (8 juillet 2026) — P2 : LOT 4 Projets + LOT 2 Timeline
### LOT 4 — Projets (CDC §6) — testé 42/42 backend + frontend 100% (iteration_4)
- ✅ Stockage médias **GridFS** (bucket `media`) : POST /api/media/upload (dédup sha256, max 80 Mo), GET /api/media/{id} (stream, sécurisé par user), GET /api/media/quota. Quotas stockage : 200 Mo free / 2 Go basic / 10 Go pro
- ✅ CRUD projets : POST /api/projects (upsert), GET liste/détail, duplicate, DELETE avec purge des médias orphelins. Quotas projets : 1 free / 10 basic / illimité pro (429 + invite upgrade)
- ✅ Studio : serializeProject/restoreProject (audio + clips perso GridFS + clips Pexels par URL + paroles + timings + style + réglages), auto-save 30 s, badge « Enregistré ✓ », upload médias en tâche de fond, ouverture via /studio?project=ID
- ✅ Page React « Mes projets » (/projects) : cartes vignette, renommer, Ouvrir/Dupliquer/Supprimer, lien navbar desktop+mobile
### LOT 2 — Timeline (CDC §4) — testé 100% frontend (iteration_5)
- ✅ 2 pistes : CLIPS (segments aimantés au beat, couleur par clip) + MOTS (libres)
- ✅ Bottom sheet segment : choix du clip (vignettes vidéo), point d'entrée (slider), 🔒 verrouiller
- ✅ state.cutOv : les segments verrouillés **survivent au 🎲 Re-tirer** ; sérialisé dans les projets
- ✅ Piste MOTS : drag des bords (timings) et déplacement, double-clic pour corriger (vide = supprimer), adoption des units comme anchors 'manual', subs.raw reconstruit
- ✅ Zoom +/−, règle graduée par beat, playhead sync lecture, seek au clic
### Dette technique notée (pour lots suivants)
- studio.html = 3546 lignes → extraire timeline.js ; bindWordDrag → AbortController ; renderTimeline → debounce rAF ; cutOv indexé par index (fragile si bpm/trim changent → indexer par timestamp) ; server.py 1560 lignes → modules
- ⚠️ Nécessite un REDÉPLOIEMENT pour beat-cut.com

## Implémenté (8 juillet 2026) — LOT 0 : synchro sous-titres
- ✅ **`remapWords` (LCS) vérifié** : la fonction d'origine EST conservée et fonctionne (preview ET prod). 11 tests unitaires couvrant les critères 2.5 du CDC (1 mot corrigé sur 50 → 49 timestamps strictement identiques ; insertion locale ; suppression sans impact ; 30% mots différents calés ; ponctuation/casse ignorées). Test permanent : `/app/frontend/tests/test_remap_words.js`
- ✅ **Mode « Colle tes paroles »** (CDC §2.4) : bouton « 📋 J'ai mes paroles — les coller » + modal. Si grille temporelle déjà détectée → calage immédiat via remapWords ; sinon → détection IA lancée automatiquement puis texte officiel posé sur les timings. Testé e2e (mots identiques = timestamps exacts, verlan/argot interpolés localement)
- ✅ **Garde-fou mode Beats** : avertissement si l'utilisateur bascule en "Beats" avec des mots calés IA (source de désync accidentelle)
- ⚠️ Nécessite un REDÉPLOIEMENT pour beat-cut.com

## Comptes seedés
Voir `/app/memory/test_credentials.md` (admin@beatcut.fr, demo@beatcut.fr)

## Backlog priorisé
- **P1** : Activer Resend dès que le domaine est prêt (remplir RESEND_API_KEY + SENDER_EMAIL dans backend/.env, redémarrer le backend — rien d'autre à faire)
- **P1** : Configurer le webhook Stripe dans le dashboard (endpoint /api/webhook/stripe, remplir STRIPE_WEBHOOK_SECRET) pour une synchro instantanée des renouvellements
- **P2** : Historique des paiements dans le dashboard ; page admin
- **P2** : Galerie de vidéos exportées (object storage) ; serveur d'extraction acapella (UVR)
- **P2** : Tester perfs MediaPipe sur mobile (Safari iOS / Chrome Android) — peut être lourd pour les vieux appareils
- **P3** : Tester l'export MP4 avec "Derrière le sujet" actif (vérifier que le MediaRecorder capture bien la composition)

## Notes
- ⚠️ STRIPE EN MODE LIVE : tout paiement complété débite une vraie carte
- Les clés Groq/Pexels sont dans backend/.env, jamais exposées au navigateur
- Emails : mode simulé (logs serveur + lien affiché) tant que RESEND_API_KEY est vide

## Implémenté (9 juillet 2026) — Studio V2 : Pexels réel, édition paroles complète, barres IA, calage amélioré
- ✅ **Pexels branché** : suppression du listener mock « Banque de clips : à brancher par Emergent » — la recherche (Entrée) appelle le proxy `/api/proxy/pexels` réel, orientation suit le format vidéo, clic vignette = ajout du clip. Testé e2e (9 vignettes).
- ✅ **Synchro paroles éditeur ↔ timeline** : correction du conflit clic/double-clic (le re-render sur simple sélection cassait le dblclick) → `syncSel()` sans re-render. Double-clic (éditeur OU bloc timeline) = édition, propagée aux deux vues. Testé e2e.
- ✅ **Ajout de mots** : boutons « + » entre les chips (hover) avec timing auto dans le trou entre voisins ; double-clic sur zone vide de la piste paroles = mot à cet instant ; Escape/vide = annulation propre. Testé e2e.
- ✅ **Barres de chargement IA** (`aiBar`, haut de page, barre rouge + pastille) : détection paroles (progression acapella par polls + transcription), « Caler mes paroles », recalage, export vidéo (progression réelle s/s). Testé visuellement.
- ✅ **Calage auto amélioré** (`refineTimings`) : début de chaque mot aimanté sur l'attaque vocale (montée d'énergie ±140 ms de l'enveloppe), durées min 80 ms, micro-trous <150 ms comblés (anti-clignotement), zéro chevauchement. Appliqué à détection/coller/recalage. ⚠️ À valider à l'oreille avec un vrai morceau.
- ✅ Textes placeholders « EMERGENT : » nettoyés (paste hint, auth hint, commentaire format Pexels)
- ⚠️ Restant mocké dans studio.html : « Série de vidéos » (genSerie/exportKept — variantes non générées réellement)
- ⚠️ Nécessite un REDÉPLOIEMENT pour beat-cut.com
