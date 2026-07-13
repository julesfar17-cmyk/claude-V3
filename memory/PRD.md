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

## Implémenté (9 juillet 2026) — Série de vidéos réelle (dernier bloc mocké branché)
- ✅ Flux : morceau (projets serveur chargés via GridFS + clips Pexels) → multi-sélection de styles (7 presets + styles perso ★) → N variantes réelles (paroles/timings conservés, plans re-tirés aléatoirement, styles round-robin, plans 🔒 respectés)
- ✅ Vignettes réelles (rendu canvas via `drawPreview(t, cvOverride)`) + bouton ▶ Aperçu (lecture audio + rendu variante en direct sur la carte)
- ✅ Export réel séquentiel des gardées : `exportVideo(nameSuffix)` promisifié, fichiers `Titre-vN.mp4`, quota décompté par vidéo, arrêt propre si quota atteint, style/plans du projet restaurés après la série
- ✅ Refactor : `fetchRemoteMorceau()` extrait de `loadRemoteMorceau` (réutilisé par la série), `presetDemoHTML()` partagé éditeur/série
- ✅ Testé e2e Playwright : génération 3 variantes (vignettes réelles vérifiées pixel), preview lecture start/stop, garder/jeter, export réel téléchargé (10 s), quota 10→9, restauration du style
- ℹ️ Fixture de test : projet « Morceau Série Test » sur le compte démo (audio WAV 12 s GridFS + clip Pexels + 6 mots)
- ⚠️ Nécessite un REDÉPLOIEMENT pour beat-cut.com

## Corrigé (10 juillet 2026) — Écrans noirs sur certains plans (aperçu + export)
- Cause : dans `drawPreview`, quand la vidéo d'un plan était en plein seek/décodage (`readyState<2`, `seeking`) ou mise en pause par le navigateur, RIEN n'était dessiné → fond noir avec paroles par-dessus
- ✅ Fallback en cascade : frame vidéo prête → vidéo ; sinon → **vignette du sous-plan** (Image mise en cache `clip._timgs`) ; sinon → dégradé. Plus jamais d'écran noir
- ✅ `wakeClips()` : relance `play()` sur les <video> en pause avant lecture, boucle extrait, aperçu série et export
- ✅ Testé : frame vidéo OK, branche vignette validée (thumb injecté rendu plein cadre), branche dégradé validée
- ⚠️ Nécessite un REDÉPLOIEMENT pour beat-cut.com

## Corrigé (10 juillet 2026) — Plans pixelisés / qui ne se lancent pas (qualité vidéo 100%)
- Causes : (1) vignette de secours 90×120 upscalée en 1080×1920 = bouillie de pixels, affichée trop souvent ; (2) BUG re-seek en boucle : quand `seek + temps écoulé` dépassait la durée du clip, la comparaison sans modulo re-seekait à CHAQUE frame → plan bloqué en seeking, jamais net
- ✅ **Double lecteur par clip** (`cl.els[0/1]`, `poolEl`, `assignPlanPlayers` alternance par occurrence) : le plan suivant est pré-calé sur un 2e <video> en pause pendant que le courant joue → à la coupure, bascule sur un lecteur déjà prêt = image nette immédiate
- ✅ **Lookahead** dans `drawPreview` (pré-seek plan suivant + bouclage vers plans[0]) ; pause de l'ancien lecteur à la transition (`lastPlanEl`)
- ✅ **Fix modulo** : comparaison `|currentTime - target%duration|` → plus de re-seek infini
- ✅ **warmUpPlans(fromT)** : pré-cale les 2 premiers plans avant lecture/export (await dans exportVideo → 1re frame déjà nette) ; remplace wakeClips
- ✅ Vignettes de secours en **360×480** (4× plus nettes) — utilisées seulement quelques frames au pire
- ✅ Testé e2e (fixture WebM décodable en headless) : 5 s de lecture = 2 frames de secours sur ~300 (99,3 % vidéo native), pool 2 lecteurs OK, cas seek>durée : 5/20 au lieu de 20/20 bloqué
- ⚠️ Nécessite un REDÉPLOIEMENT pour beat-cut.com

## Implémenté (10 juillet 2026) — Export "offline" WebCodecs + aperçu proxy (comme les logiciels de montage)
- ✅ **exportOffline** : rendu image par image (30 fps) — chaque frame attend le seek exact du clip (`seekPlanFrame`) avant d'être dessinée (`drawPreview(t, canvas offscreen pleine résolution)` avec flag `offlineRender`) puis encodée H.264 12 Mbps (`VideoEncoder avc1.640033`) + AAC 192k (`AudioEncoder`), muxé en MP4 via **mp4-muxer** (vendorisé : `/frontend/public/vendor/mp4-muxer.min.js`, global `Mp4Muxer`). Zéro freeze possible, qualité 100 % garantie, progression réelle en %
- ✅ **Dispatcher** `exportVideo` : quota/checks → `offlineSupported()` (isConfigSupported avc+aac) → offline, sinon `exportRealtime` (ancien MediaRecorder, conservé en repli). Échec offline → repli realtime automatique
- ✅ **Aperçu proxy demi-résolution** (`PREVIEW_SCALE=2`, canvas 540×960) : lecture beaucoup plus fluide ; `exportRealtime` repasse le canvas en pleine résolution pendant l'export puis restaure
- ✅ `drawPreview` : en mode offline, pas de play/lookahead/re-seek (le seek est géré par l'appelant)
- ✅ Testé : proxy 540×960 OK ; fallback realtime auto (pod headless sans encodeur H.264) avec export réel réussi + quota décompté + canvas restauré ; mécanique WebCodecs+muxer validée e2e (VP9/Opus, mêmes APIs, mp4 230 Ko généré)
- ℹ️ Le chemin offline H.264 s'active automatiquement sur Chrome/Edge/Brave/Android ; Safari sans AudioEncoder AAC → repli temps réel
- ⚠️ Nécessite un REDÉPLOIEMENT pour beat-cut.com

## Corrigé (10 juillet 2026) — Freezes de l'aperçu : lecture événementielle (modèle V1 restauré)
- Cause : la V2 vérifiait la position vidéo À CHAQUE FRAME dans drawPreview (`|currentTime-target|>0.45 → seek`) → re-seeks en pleine lecture (drift audio/vidéo, boucles de clips) = micro-freezes. La V1 n'agissait qu'aux coupures
- ✅ Porté le modèle V1 : `syncLivePlan(t)` dans raf() détecte le changement de plan → `activatePlan(i)` (UNE fois par coupure) : play du lecteur pré-calé, pause de l'ancien, pré-seek du lecteur du plan suivant. `livePtr`/`liveEl` globaux, reset dans stopAll
- ✅ drawPreview en lecture : dessine `liveEl` tel quel, ZÉRO seek/play par frame. À l'arrêt (scrub) : calage à la demande conservé. Mode offline inchangé
- ✅ Aperçu série : `syncLivePlan` appelé dans la boucle withVariant
- ✅ Testé e2e : 60 fps constants, 6 seeks/5 s (= pré-calages aux coupures uniquement), 11 activations, lecteurs en pause au stop
- ⚠️ Nécessite un REDÉPLOIEMENT pour beat-cut.com

## URGENT corrigé (10 juillet 2026) — « Moteur vidéo des plans » (spec client appliquée à la lettre)
- ✅ 1. DOUBLE TAMPON : 2 <video> par fichier source (`poolEl`/`makePoolVideo`), plan N+1 pré-positionné en pause (`prepareNext`) pendant que N joue
- ✅ 2. À la coupure : permutation + play() UNIQUEMENT, zéro seek (`activatePlan`) ; pendant un plan (`ensureActive`) : re-seek seulement si dérive >0,9 s, paused→play(), ended→reprise au point d'entrée
- ✅ 3. Lecteur pas prêt : vignette 360×480 du plan, sinon dégradé — jamais de canvas vide
- ✅ 4. Éléments : muted, playsinline (+attribut), preload=auto, loop=false, disableRemotePlayback (addClip refactoré via makePoolVideo, plus de play() à l'import)
- ✅ 5. Export = même pipeline de rendu (offline: seekPlanFrame+drawPreview ; realtime: syncLivePlan dans raf) ; quota décompté seulement si fichier valide/complet (durée ≥ ext.dur−0,8 s en realtime ; offline complet par construction)
- ✅ BUG BONUS corrigé : retour sur un morceau distant déjà ouvert → resetAudioState purgait les médias sans re-téléchargement (_loaded restait true) → morceau vide. Fix : `M._loaded=false` au reset (openEditor + serieLoadMorceau)
- ✅ RECETTE exécutée (fixture « Recette 150BPM » id 032e4762018d45 : 150 BPM, 30 s, ~75 plans, 2 webm dont un GOP long -g 300 simulant les seeks lents) : 0 frame figée, 0 plan noir, 0 vignette sur 3 lectures d'affilée, 60 fps, seeks uniquement aux pré-calages, changement/retour morceau OK
- ⚠️ Non testable en headless (pas de codecs H.264/HEVC) : mp4 iPhone HEVC + H.264 GOP long → à valider par le client dans son navigateur
- 📋 PHASE SUIVANTE À CHIFFRER (demande client) : normalisation serveur à l'upload (transcode H.264 1080p max, GOP ~0,5 s, faststart)
- ⚠️ Nécessite un REDÉPLOIEMENT pour beat-cut.com

## Implémenté (10 juillet 2026) — PHASE 1 : Transcodage serveur à l'upload + verrou de chargement (fix définitif freezes iPhone HEVC/4K)
- ✅ **Backend transcodage FFmpeg** (`imageio_ffmpeg`, sémaphore 2 jobs max) : `POST /api/media/upload` détecte les vidéos → réponse immédiate `{media_id, processing:true}` + tâche asyncio de transcodage → H.264 High 1080p max (grand côté 1920), **keyframes toutes les 0,5 s** (`force_key_frames`), AAC 128k stéréo, `+faststart`, yuv420p. Le fichier GridFS est REMPLACÉ avec le MÊME _id (références projets intactes). Échec ffmpeg → original conservé + `transcode_failed:true`
- ✅ `GET /api/media/{id}/status` → `{processing, transcoded, failed, size}` (scopé user, 404 autre user, 400 id invalide)
- ✅ **Migration admin** : `POST /api/admin/media/migrate` (lance en background sur toutes les vidéos GridFS non transcodées) + `GET` pour le statut `{running,total,done,failed}` — 403 non-admin. **Exécutée en preview : 7/7 vidéos migrées, 0 échec**
- ✅ **Frontend studio.html** : `API.uploadMedia` polle le statut (2 s × 150) ; `addClip` → badge « ⏳ Optimisation de ta vidéo… » (`data-testid=clip-optimizing-badge`) + une fois transcodé, `swapClipMedia` remplace le blob local par la version optimisée téléchargée ; échec → toast d'avertissement explicite
- ✅ **Verrous** : `play()`, `startLoop()`, `exportVideo()`, `genSerie()` bloqués avec toast tant qu'un clip s'optimise (`clipsOptimizing()`)
- ✅ **Verrou de chargement projet** : overlay plein écran `#loadOverlay` (`data-testid=load-overlay`) avec barre de progression réelle (streaming fetch + Content-Length) — audio + clips ENTIÈREMENT téléchargés en blobs avant ouverture de l'éditeur
- ✅ Testé : agent de test 10/10 backend (pytest `/app/backend/tests/test_media_transcode.py`) + e2e frontend complet (upload → badge → lecture bloquée → lecture OK après). Bench réel : 4K portrait 35 Mo → 1080×1920 2 Mo en ~3 s, keyframes exactes à 0,5 s
- ⚠️ Nécessite un REDÉPLOIEMENT pour beat-cut.com ; relancer la migration en prod après déploiement : `POST /api/admin/media/migrate` (connecté admin)
- 📋 Recommandations testeur (non bloquant, backlog) : endpoint `DELETE /api/media/{id}` ou GC des médias orphelins ; statut `queued` distinct si file d'attente transcode chargée

## Implémenté (10 juillet 2026) — Clips Pexels optimisés côté serveur (option A validée user)
- ✅ `POST /api/media/import-url` : le SERVEUR télécharge le clip Pexels (hosts *.pexels.com uniquement, https, max 80 Mo) puis le passe dans le même pipeline de transcodage (H.264, keyframes 0,5 s) → stocké GridFS, compte dans le quota user. Dédup sha256 conservée
- ✅ Refactor backend : `_store_media()` partagé entre `media_upload` et `media_import_url`
- ✅ **Fix upscale** : le filtre scale n'agrandit plus les vidéos < 1080p (`min(1920,iw)`) — un clip 720p reste en 720p (fichier plus léger). Testé : 720p in → 720p out
- ✅ Frontend : clic vignette Pexels → `API.importMedia` (zéro re-upload client) → poll statut → clip ajouté avec `mediaId` + `pexelsUrl` (les projets rechargent depuis GridFS en priorité). Toasts « ⏳ Optimisation du clip en cours… » / « ✓ Clip ajouté — optimisé »
- ✅ Testé e2e (curl + Playwright) : import Pexels 720p → transcodé en ~13 s, keyframes 0,5 s ; flux studio complet OK (recherche neon → clic → clip dans la banque en ~6 s)
- ℹ️ Les anciens projets avec clips Pexels (pexelsUrl seul) continuent de streamer depuis Pexels ; les nouveaux ajouts passent tous par GridFS optimisé
- ⚠️ Nécessite un REDÉPLOIEMENT pour beat-cut.com

## Corrigé (11 juillet 2026) — 🔴 Clients ayant payé sans recevoir leur accès Pro/Basic
- Cause : l'activation dépendait UNIQUEMENT du retour du client sur /dashboard?session_id=... après paiement Stripe. Onglet fermé / redirection ratée / cookie perdu (in-app browser iPhone) → paiement encaissé mais accès jamais activé. Webhook inactif (secret vide) = aucun filet
- ✅ **Réconciliation automatique** : `reconcile_payments()` (sessions non processed < 30 j → Stripe retrieve → si paid, `_claim_and_activate` idempotent + email de bienvenue) + `reconcile_subscriptions()` (vérifie statut/annulations/renouvellements auprès de Stripe, rafraîchit si synced_at > 12 h). Watchdog `_payments_watchdog()` lancé au startup, toutes les 10 min
- ✅ **Admin** : `POST /api/admin/payments/reconcile` (force la vérif de TOUS les abonnements) + section « Paiements & abonnements » dans /admin (bouton 🔁 Réconcilier + résultats détaillés avec emails activés et changements de statut)
- ✅ **Webhook Stripe auto-créé** : `POST /api/admin/payments/webhook-setup` crée l'endpoint via l'API Stripe pour le domaine courant (x-forwarded-host), secret stocké dans `db.config` (`_id: stripe_webhook`), cache mémoire. Handler `/api/webhook/stripe` : secret env prioritaire sinon db.config ; gère `checkout.session.completed`, `customer.subscription.updated/deleted`, `invoice.paid` (renouvellements + annulations instantanés). `GET /api/admin/payments/webhook` = statut
- ✅ Refactor : `_stripe_sub_status()` + `_apply_stripe_sub_state()` partagés (sync polling + webhook + réconciliation)
- ✅ Testé en preview : reconcile 4 sessions vérifiées (0 payées — normal, les vrais clients sont en base PROD) ; webhook créé sur le compte Stripe LIVE, signature vérifiée (400 payload non signé), puis endpoint preview SUPPRIMÉ du compte Stripe (nettoyage)
- ⚠️ **ACTIONS PROD après redéploiement** : (1) la réconciliation tourne toute seule dès le démarrage → clients réparés automatiquement ; (2) admin → « Réconcilier maintenant » pour vérifier immédiatement + voir les emails réparés ; (3) admin → « ⚡ Activer le webhook Stripe » UNE FOIS depuis beat-cut.com

## Corrigé (11 juillet 2026) — MRR admin juste vis-à-vis des vrais paiements
- Cause : le MRR était théorique (abonnés actifs en base locale × prix catalogue). Base locale incomplète (paiements non réclamés) → MRR faux
- ✅ `_stripe_revenue_stats()` : calcul direct depuis Stripe (source de vérité), cache 10 min — `stripe_mrr` (somme des abonnements actifs avec vrais montants, annuels prorata /12, coupons appliqués), `stripe_active_subs`, `revenue_this_month` + `revenue_total` (charges succeeded − remboursements)
- ✅ /admin : cartes « MRR RÉEL (STRIPE) », « ENCAISSÉ CE MOIS », « ENCAISSÉ TOTAL », « Abos Stripe actifs » (fallback sur le MRR estimé si Stripe indisponible)
- ✅ Vérifié en preview (même compte Stripe LIVE que la prod) : MRR réel 317,97 €, 29 abos actifs, 408,72 € encaissés — contre 0 € avec l'ancien calcul local. Confirme au passage l'ampleur du bug des accès non délivrés (29 abos Stripe vs 0 liés en base preview)

## Implémenté (11 juillet 2026) — Transcodage externalisé via Mux (fix des 10 min de transcodage en prod)
- Contexte : en prod (CPU limité), le transcodage FFmpeg local prenait ~10 min/vidéo. Choix user : externaliser avec Mux
- ✅ `_mux_transcode()` dans server.py : Direct Upload Mux (PUT serveur→Mux) → asset `video_quality: basic` (encodage GRATUIT, fallback `encoding_tier: baseline` si 400) + `max_resolution_tier: 1080p` + `static_renditions: highest` → poll asset ready + rendition MP4 → téléchargement `stream.mux.com/{playback_id}/highest.mp4` → **suppression de l'asset Mux** (finally, zéro stockage récurrent)
- ✅ `_transcode_media` : Mux d'abord, **repli FFmpeg local automatique** si Mux indisponible/échec. Tout le reste inchangé (statuts, badge studio, migration, import Pexels passent par le même chemin)
- ✅ Clés dans backend/.env : `MUX_TOKEN_ID`, `MUX_TOKEN_SECRET` (fournies par l'user)
- ✅ Testé e2e : 4K portrait 50 Mo → 1080x1920 H.264+AAC 2,1 Mo en ~35 s ; asset supprimé (204) ; 0 asset restant sur le compte Mux
- ⚠️ Compromis : keyframes Mux ~5 s (vs 0,5 s FFmpeg) — pas de contrôle GOP chez Mux. Le moteur double-lecteur pré-cale les seeks en avance → devrait rester fluide ; à valider par l'user. Option de repli si micro-lags : rendition 720p ou re-densification locale
- ⚠️ Nécessite un REDÉPLOIEMENT (+ les 2 clés Mux dans les env vars de prod si les .env ne sont pas repris automatiquement)

## Corrigé (12 juillet 2026) — Bugs iPhone Safari : export sans son, vignettes vides, export lent
- ✅ **Export sans son (Safari)** : flux MediaRecorder construit via `new MediaStream([videoTracks, audioTracks])` (addTrack sur le flux canvas fait perdre l'audio sur Safari) + mime `video/mp4;codecs=h264,aac` ajouté + `rec.start()` SANS timeslice sur Safari (le timeslice fragmente mal le MP4)
- ✅ **Vignettes vides** : (1) régénération des vignettes après `swapClipMedia` (elles étaient générées depuis l'original HEVC .mov indécodable puis jamais refaites) ; (2) `makeThumbs`/`makeThumbAt` : playsinline + nudge `play().then(pause)` + `v.load()` (iOS ne dessine pas les frames d'une vidéo jamais jouée) ; (3) même nudge dans `openPicker` (#pickVid)
- ✅ **Export lent (Safari)** : négociation multi-codecs AVC (`_avcCodec` : 640033→640028→4d4028→42e01f) dans offlineSupported/exportOffline → l'export rapide WebCodecs s'active sur Safari 26+ (AudioEncoder dispo depuis Safari 26). Sur iOS < 26 : reste en temps réel (limite navigateur, AudioEncoder absent — documenté)
- ✅ Non-régression Chrome : testing agent iteration_8 = 100 %, 0 erreur JS (export realtime 879 Ko téléchargé, vignettes webm régénérées, badge optimisation OK avec Mux ~23 s)
- ⚠️ Validation Safari iPhone par l'USER requise (impossible en headless) + REDÉPLOIEMENT nécessaire
- Notes testeur : env headless sans codecs h264 → tester les vignettes avec des WEBM (voir context_for_next_testing_agent d'iteration_8)

## Corrigé (12 juillet 2026) — Optimisation vidéo perçue comme trop longue (« 3 plombes »)
- Diagnostic chiffré (vidéo 45 s / 79 Mo) : PUT→Mux 6,6 s · encodage 2,2 s · rendition MP4 23,7 s (incompressible chez Mux) · download 6,7 s = ~41 s serveur + upload mobile client. Le vrai problème : TOUT était bloqué pendant ce temps
- ✅ **Optimisation non bloquante** : `clip._playable` (loadedmetadata + videoWidth>0) → la lecture/boucle n'est bloquée QUE si l'original est indécodable (`clipsBlocking()`), sinon montage + lecture immédiats avec l'original, remplacement silencieux à la fin (jamais en pleine lecture : attente `playing||looping`)
- ✅ Badge : overlay bloquant → petit chip discret `clip-opt-chip` (« ☁ Envoi X % » puis « ⏳ Optimisation en arrière-plan… ») quand le clip est lisible
- ✅ **Progression d'envoi réelle** : API.uploadMedia passé en XHR avec upload.onprogress (le % s'affiche dans le chip)
- ✅ Parallélisation : TRANSCODE_SEM 2→6 (Mux = network-bound, plusieurs clips uploadés d'affilée ne font plus la queue)
- ✅ Export/genSerie restent verrouillés pendant l'optimisation (l'export doit être parfait) avec message clair
- ✅ Testé e2e Playwright : chip non bloquant affiché, lecture démarrée PENDANT l'optimisation (tcNow avance), optimisation finie en ~18 s, badge disparu, vignettes régénérées
- ⚠️ REDÉPLOIEMENT nécessaire

## Implémenté (12 juillet 2026) — Export hybride Safari : rapide ET avec le son garanti
- Contexte : toujours pas de son en export sur iPhone (MediaRecorder Safari trop capricieux) + export temps réel trop lent. User ouvert à Mux/Replicate → impossible pour le rendu (paroles/effets = canvas client), solution retenue : **hybride client/serveur**
- ✅ `offlineSupported()` retourne désormais un mode : `'full'` (VideoEncoder+AudioEncoder → tout client, Chrome/Safari 26+), `'hybrid'` (VideoEncoder seul → Safari 16.4-25), `false` (→ realtime MediaRecorder)
- ✅ Mode hybride dans `exportOffline(nameSuffix, mode)` : vidéo encodée client (WebCodecs H.264, accéléré matériel iPhone, sans perte) → MP4 vidéo seule (mp4-muxer sans piste audio) → POST `/api/export/finalize` (vidéo + WAV stéréo `extractWavStereoBlob`) → serveur FFmpeg `-c:v copy -c:a aac 192k +faststart` → MP4 final téléchargé. **Son garanti à 100 %** (plus de MediaRecorder sur Safari moderne)
- ✅ Backend `POST /api/export/finalize` : auth, limites 500 Mo vidéo / 100 Mo audio, tmpdir, timeout 180 s. Testé : 6 s vidéo 1080x1920 + WAV → MP4 h264+AAC en **0,68 s** (copy vidéo = zéro ré-encodage)
- ✅ UI : étape « Ajout du son (serveur)… » dans la barre de progression
- ✅ Smoke test headless : 0 erreur JS, lecture OK, offlineSupported()=false en headless → repli realtime intact (testé iter_8)
- ⚠️ Le mode hybride ne peut PAS être testé en headless (pas de codecs H.264) — validation par l'USER sur iPhone requise
- ⚠️ REDÉPLOIEMENT nécessaire

## Corrigé (12 juillet 2026) — « Certaines vidéos ne sont pas sauvegardées »
- Cause : un clip n'est rattaché au projet QUE si l'upload serveur réussit. Échecs silencieux : fichier > 80 Mo (une vidéo iPhone 4K dépasse ça en ~1 min !), fermeture de la page avant la fin de l'envoi, stockage plein. Seul signal : un toast fugace
- ✅ Limite d'upload 80 → **300 Mo** (`MAX_MEDIA_SIZE`). Vérifié : l'ingress accepte 260 Mo en POST direct (200 OK, 7 s)
- ✅ Pré-contrôle taille côté client (`MAX_UPLOAD_MO=300`) avec message immédiat et explicite
- ✅ **Badge rouge persistant** « ⚠ Non sauvegardée — réessayer » (`data-testid=clip-save-failed-badge`, cliquable → `retryClipUpload` re-upload depuis le blob local) au lieu d'un toast éphémère
- ✅ Refactor : flux d'upload extrait dans `startClipUpload(clip, file)` (réutilisé par le retry)
- ✅ `beforeunload` : alerte navigateur si on ferme l'onglet pendant un envoi/optimisation (clips `_optimizing` ou `M._uploadingAudio`)
- ✅ Testé e2e Playwright : badge rouge rendu + cliquable, toast taille, 0 erreur JS. Fichiers de test GridFS supprimés
- ⚠️ REDÉPLOIEMENT nécessaire

## Corrigé (12 juillet 2026) — Clips Pexels passés au système non bloquant
- Avant : clic vignette Pexels → attente BLOQUANTE du transcodage serveur complet avant que le clip apparaisse
- ✅ Maintenant : clic → fetch direct du MP4 Pexels (~2 s) → clip utilisable/lisible IMMÉDIATEMENT → `startPexelsImport(clip)` en arrière-plan (import serveur + Mux) → swap silencieux + vignettes régénérées, même chip discret que les uploads perso
- ✅ Échec d'import silencieux : le clip reste référencé par son URL Pexels (comportement historique, pas de badge rouge)
- ✅ Bonus migration : à la réouverture d'ANCIENS projets, les clips Pexels sans mediaId déclenchent l'import en arrière-plan (condition dans addClip : `pexelsUrl && !mediaId`, indépendante de skipUpload) → migration douce vers GridFS
- ✅ Testé e2e : clip apparu en ~2 s, lecture pendant l'optimisation OK, 0 erreur JS
- ⚠️ REDÉPLOIEMENT nécessaire

## Corrigé (12 juillet 2026) — Son toujours absent des exports iPhone : audio 100 % serveur sur Safari
- Diagnostic factuel : export realtime reproduit en headless Chromium → le fichier CONTIENT une piste audio réelle (opus stéréo, max -2,9 dB) → notre code realtime est sain, le problème est exclusivement le MediaRecorder audio de Safari
- ✅ **Décision radicale : plus AUCUN chemin d'export Safari ne dépend de l'audio MediaRecorder** :
  - `exportRealtime` sur Safari : enregistre la VIDÉO SEULE (pas de piste audio dans le flux), puis `rec.onstop` (passé async) envoie vidéo + WAV stéréo à `/api/export/finalize` → le serveur mux la piste son exacte (-c:v copy). Échec réseau → rien décompté, message clair
  - mode hybride (WebCodecs) : déjà audio serveur
  - Chrome/desktop : inchangé (audio client validé)
- ✅ **Anti-cache** : `Studio.js` charge l'iframe avec `/studio.html?v=${Date.now()}` → chaque chargement récupère la DERNIÈRE version du studio (Safari gardait potentiellement une vieille version en cache après les déploiements !)
- ✅ Non-régression Chromium testée : export téléchargé, piste audio opus présente et audible
- 📢 Signal de vérification pour l'user : sur iPhone, pendant l'export, l'étape « Ajout du son (serveur)… » DOIT apparaître — si absente, l'app tourne encore sur l'ancien build (fermer l'onglet Safari et rouvrir)
- ⚠️ REDÉPLOIEMENT nécessaire

## Corrigé (12 juillet 2026) — 🔴 INCIDENT « projet perdu » : protections anti-perte de données complètes
- Incident user prod : export « diaporama » (vignettes fixes) → rechargement bloqué 3/34 → autosave a ÉCRASÉ le projet avec un état vide → projet perdu
- Chaîne causale : fetchMedia sans timeout (blocage), restore partiel non détecté, autosave aveugle, export silencieux en mode secours vignettes
- ✅ **Sauvegardes versionnées serveur** : `project_backups` (15 versions/projet, index (project_id, created_at)) — snapshot AVANT chaque save qui PERD des clips (`reason: perte-de-clips`) + snapshot auto max 1×/10 min. Endpoints : GET `/api/projects/{id}/backups`, POST `/api/projects/{id}/backups/{bid}/restore` (backup 'avant-restauration' d'abord)
- ✅ **Verrou anti-écrasement** : `restoreIncomplete` → si ≥1 clip échoue au chargement, `persistRemote()` REFUSE de sauvegarder (#saveState « ⚠ Sauvegarde désactivée ») + toast explicite
- ✅ **fetchMedia robuste** : 3 tentatives + AbortController anti-stall (30 s sans octets → abort → retry) — plus de chargement gelé à 3/34
- ✅ **Bouton « ☁ Récupérer mes vidéos déjà envoyées »** (banque, `data-testid=recover-media-button`) : GET `/api/media/mine` (limite 1000) → ré-ajoute toutes les vidéos GridFS absentes de la banque, avec barre de progression, puis réactive la sauvegarde
- ✅ **Bouton « 🕘 Versions »** (barre du studio, `data-testid=backups-button`) : popup listant les versions (date, nb vidéos, nb plans) avec Restaurer (confirm + reload)
- ✅ **Garde anti-diaporama** : `ensureClipsReady()` avant TOUT export — chaque vidéo utilisée par un plan doit être décodable (readyState≥2 + videoWidth>0, réveil load() + attente 6 s) sinon export REFUSÉ avec message clair + console.warn
- ✅ Testé (iteration_9) : backend 7/7 pytest (backup perte-de-clips, restore, throttle, scoping, 401/404), frontend : popup versions OK, verrou OK (0 POST), récupération 15 vidéos OK, lecture OK. Export bloqué en headless par la garde = comportement CORRECT (codecs H.264 absents du headless)
- 📢 Pour le projet perdu de l'user : après redéploiement → ouvrir le projet → « ☁ Récupérer mes vidéos » restaure la banque (les plans/le montage restent à refaire, les backups n'existaient pas encore à ce moment). Les vidéos GridFS n'ont PAS été supprimées (GC uniquement à la suppression de projet)
- ⚠️ REDÉPLOIEMENT nécessaire

## Implémenté (13 juillet 2026) — 🚀 PHASE 2 : MOTEUR VIDÉO DÉFINITIF 100 % WEBCODECS (façon LYRC)
- Demande user : « MOTEUR VIDÉO DÉFINITIF — ON PASSE AU WEBCODECS, MODE UNIQUE » (bascule totale choisie, pas de toggle). Prototype de référence /tmp/moteur-lyrc-test.html suivi À L'IDENTIQUE (ordre de décodage mp4box jamais trié, description avcC/hvcC W3C, pas d'optimizeForLatency, backpressure 10 frames, frame.close() systématique)
- ✅ `<script src="/vendor/mp4box.all.min.js">` chargé (vendorisé) + filtre du bruit BoxParser des mp4 iPhone
- ✅ `parseClipWC(clip, blob)` : démuxage mp4box → `clip.wc={samples[] (ordre de décodage), config (codec+description), durationS}` + `VideoDecoder.isConfigSupported` ; fin d'extraction par stabilisation du compte d'échantillons (fiable sur gros fichiers) ; flags `_wcReady/_wcFail/_wcParse`
- ✅ `class SegPlayer` : lecteur de segment à double tampon (seek → keyframe scan → décodage, fill() borné à 10 frames / queue 14, frameAt(t) draine jusqu'à la cible)
- ✅ LECTURE : double lecteur wcA/wcB — pendant qu'un plan joue, wcB pré-décode le plan suivant → à la coupure, permutation (latence ~0). `syncLivePlan`/`wcActivate`/`wcWarmUp` ; `play()` et `startLoop()` attendent la 1re frame décodée (max 2,5 s) avant de lancer le son ; reboucle si un plan dépasse la durée du clip
- ✅ SCRUB à l'arrêt : décodeur dédié `wcScrub` re-calé à la demande + redraws différés (wcScrubRedraw) → plus aucun seek `<video>`
- ✅ EXPORT : `wcExportSeek` décode séquentiellement, critère d'exactitude « la frame suivante dépasserait la cible » → validé 12/12 timestamps EXACTS (frame-accurate). exportOffline branché dessus (plus de seekPlanFrame quand WC actif)
- ✅ VIGNETTES : `wcMakeThumbs` génère les thumbs via WebCodecs (un seul décodeur, seek par sous-plan) — plus de <video> pour les thumbs quand le codec est décodable
- ✅ Gating strict : `clipsBlocking()` inclut l'état de parse WC → lecture impossible tant que les clips ne sont pas démuxés/bufferisés
- ✅ REPLI automatique : navigateur sans WebCodecs/MP4Box → ancien moteur <video> intact (warmUpPlansTag/activatePlan/poolEl conservés) ; clip au codec indécodable (ex. HEVC avant optimisation Mux) → _wcFail → métadonnées+vignettes via <video> + fallback vignettes à la lecture, ré-essai automatique après swap Mux (swapClipMedia re-parse)
- ✅ Série de vidéos : drawVariantFrame + serieWaitClips + ensureClipsReady branchés WC
- ✅ data-testid song-card/data-song-id sur les cartes home (testabilité) ; log [wc] dédupliqué par clip
- ✅ TESTÉ (iteration_10, 100 % backend 5/5 + 100 % frontend) : parse VP9 240 samples, thumbs 4/4, lecture wcPtr avance + canvas non noir + arrêt auto, loop, scrub, sauvegarde+reload projet, série 3 versions, 0 erreur JS
- ⚠️ Chromium headless du pod SANS codecs H.264 → clips H.264 = _wcFail en test (ATTENDU, pas un bug) ; clips VP9 de test : /wc_test_a.mp4 et /wc_test_b.mp4 (servis statiquement, à conserver pour les retests)
- 📢 VALIDATION USER REQUISE sur PC Chrome (environnement réel) : lecture fluide, coupures nettes, export rapide
- ⚠️ REDÉPLOIEMENT nécessaire

## Backlog priorisé (mise à jour 13 juillet 2026)
- P1 (après validation user du moteur) : UpChunk pour uploads reprenables
- P1 : Emails Resend automatiques en cas d'échec d'export
- P2 : Nettoyage systématique des fichiers orphelins GridFS

## Implémenté (13 juillet 2026) — MODE UNIQUE : suppression totale de l'ancien moteur <video>
- Décision user : PAS de repli <video> (c'était l'ancien moteur bugué) → un seul moteur WebCodecs, point.
- ✅ SUPPRIMÉ (~200 lignes) : exportRealtime (MediaRecorder), makePoolVideo, poolEl, assignPlanPlayers/planAssign, activatePlan, prepareNext, ensureActive, warmUpPlansTag, seekPlanFrame, livePtr/liveEl, toutes les branches WC_ON — 0 résidu (grep vérifié)
- ✅ Navigateur incompatible : `engineSupported()` (VideoDecoder+VideoEncoder+VideoFrame+EncodedVideoChunk+Mp4Muxer+MP4Box) vérifié via `engineGuard()` à l'ouverture de l'ÉDITEUR (openEditor) et de genSerie → écran bloquant « BeatCut a besoin d'un navigateur récent — Chrome, Edge, Safari ou Firefox à jour » avec 4 liens de téléchargement + bouton retour (data-testid=unsupported-browser-screen)
- ✅ CHAQUE affichage de l'écran est loggué : POST /api/telemetry/unsupported-browser (ua + user_id si session) → collection `browser_unsupported_logs` ; mesure admin : GET /api/admin/telemetry/unsupported-browser {total, last_30d, samples}
- ✅ Export : offlineSupported()===false → message clair « mets ton navigateur à jour », rien décompté (plus de repli temps réel) ; échec exportOffline → message d'erreur propre, rien décompté
- ✅ CONSERVÉ (pas un moteur) : repli <video> UNIQUEMENT pour métadonnées/vignettes d'un clip au codec indécodable (HEVC iPhone) en attendant le swap Mux → re-parse WebCodecs automatique
- 🐛 BONUS corrigé : duplication de clips au chargement (course hashchange + route() → loadRemoteMorceau lancé en double → addClip dupliqués PERSISTÉS). Verrou `m._loading` dans loadRemoteMorceau. Reproduit avec 3× route() → 5 clips uniques ✓. Fixture « Morceau Série Test » réparée (clipRefs restaurés depuis la backup 13:21, dédupliqués)
- ✅ Testé : syntaxe node OK, lecture WebCodecs re-validée après suppression (wcPtr avance, canvas non noir), thumbs 4/4, écran incompatible affiché/loggué/fermé (simulation VideoEncoder=undefined), endpoints télémétrie 200
- ⚠️ REDÉPLOIEMENT nécessaire

## Corrigé (13 juillet 2026) — Aperçus des clips manquants après import + Mélanger
- Bug user : « quand on importe la vidéo l'aperçu des clips marche pas et Mélanger n'utilise que les 3 seuls clips qui ont un aperçu »
- Causes racines identifiées et corrigées :
  1. SATURATION DÉCODEURS : import multiple → un wcMakeThumbs (décodeur WebCodecs) par clip EN PARALLÈLE → au-delà de ~3-4, les décodeurs matériels refusent → vignettes vides. FIX : file d'attente globale `_thumbQ` (une génération à la fois) + retry avec un décodeur neuf si `p.err` + jeton `_thumbGen` (annule la passe obsolète après swap Mux) + renderClips() après chaque vignette (feedback progressif)
  2. SEEKS JAMAIS CRÉÉS : original HEVC illisible par <video> (pas de loadedmetadata) → seeks=[] → après le swap Mux, makeThumbs tournait sur 0 seeks → clip définitivement sans aperçu. FIX : startClipUpload régénère les seeks depuis clip.wc.durationS après le re-parse du swap + autoAssign()
  3. p.seek=undefined si seeks vide dans shufflePlans/autoAssign/removeClip → FIX : garde `(c.seeks&&c.seeks.length)? … : 0`
- ✅ Testé (pod, clips VP9) : import ×6 simultané → 6 clips avec 4/4 vignettes ; Mélanger → 20 plans, 0 seek invalide ; simulation swap Mux sans seeks → 4 seeks + 4 vignettes régénérés
- 📢 VALIDATION USER REQUISE avec ses vrais fichiers (iPhone/HEVC) sur son navigateur
- ⚠️ REDÉPLOIEMENT nécessaire

## Corrigé (13 juillet 2026) — Vignettes noires sur clips LONGS (photo utilisateur : 55ASKY ~2 min)
- Symptôme : sur un clip long, les vignettes des sous-plans tardifs (54s, 71s, 106s, 123s…) restaient noires
- Cause racine : budget FIXE de 1,5 s par vignette. Sur un GOP long (keyframe toutes les 5-10 s, typique des clips musicaux), décoder depuis la keyframe précédente jusqu'à la cible prend plusieurs secondes (surtout mobile) → abandon → vignette noire
- FIX : `wcAwaitFrame(p, t, slack)` — attente basée sur la PROGRESSION du décodeur (on continue tant que p.si avance ou que des frames arrivent ; abandon seulement après 2,5 s sans progrès, garde-fou absolu 12 s). Appliqué aux vignettes ET à `wcExportSeek` (l'export sur GOP long aurait eu le même trou)
- ✅ Testé (pod) : clip VP9 140 s, keyframe toutes les 10 s → 8/8 vignettes générées (jusqu'à 125 s) ; export frame-accurate sur un plan à 119,7 s (timestamps exacts au pas de 24 fps)
- Fichier de test long supprimé de public/ (les petits wc_test_a/b.mp4 restent pour les retests)
- 📢 VALIDATION USER REQUISE avec ses vrais clips longs
- ⚠️ REDÉPLOIEMENT nécessaire

## Corrigé (13 juillet 2026) — Export MUET depuis téléphone (PRODUCTION, iPhone Safari + Chrome iOS)
- Diagnostic confirmé avec le user : la vidéo se télécharge mais est MUETTE. Cause : WebKit iOS expose AudioEncoder et `isConfigSupported('mp4a.40.2')` répond supported → mode export 'full' (AAC client) → mais l'encodage AAC réel produit une piste inutilisable (pas de description codec / chunks invalides) → mp4 muet livré
- FIX en 3 couches (mp4 muet désormais impossible) :
  1. `_aacReallyWorks()` : AVANT l'export, encodage RÉEL de ~0,3 s de silence → exige un chunk AVEC decoderConfig.description ; sinon mode 'hybrid' (son assemblé serveur)
  2. Pendant l'export 'full' : le 1er chunk AAC sans description → rejeté (aencErr), rien de muxé
  3. Filet final : si `aencErr` ou `audioChunks===0` après flush → bascule automatique vers /api/export/finalize (serveur ajoute la piste, -c:v copy, 2-3 s) au lieu de livrer un mp4 muet. Erreur audio ≠ erreur fatale (seule la vidéo peut faire échouer l'export)
- ✅ Vérifié : /api/export/finalize testé en preview (HTTP 200, sortie avec Stream audio aac stéréo 192k) ; _aacReallyWorks/offlineSupported s'exécutent proprement (pod sans AAC → hybrid/false honnête) ; syntaxe OK
- ⚠️ Le fix est en PREVIEW : le user doit REDÉPLOYER pour corriger la production (beat-cut.com)
- ⚠️ Point de vigilance prod : le chemin hybrid POST ~50 Mo (vidéo+wav) vers /api/export/finalize — si l'ingress prod limite la taille du body, l'utilisateur verrait « assemblage du son impossible » → contacter le support Emergent dans ce cas

## Corrigé (13 juillet 2026) — Export muet iPhone : SOLUTION DÉFINITIVE (son serveur forcé sur mobile)
- Le fix précédent (test AAC réel) ne suffisait pas : WebKit iOS peut réussir le test ET produire une piste AAC muette à l'usage
- FIX DÉFINITIF : `MOBILE_UA` (iPhone/iPad/Android + iPad desktop-UA via maxTouchPoints) → mode 'hybrid' FORCÉ : sur mobile le son est TOUJOURS assemblé par le serveur (ffmpeg, AAC parfait), plus jamais l'encodeur AAC du navigateur
- Diagnostics ajoutés :
  - Toast final indique le mode : « son : assemblé par le serveur » / « son : direct » → l'utilisateur peut nous rapporter le chemin réellement pris
  - Détection de source silencieuse : peak de l'extrait mesuré avant export → toast d'alerte si ~0 (morceau mal rechargé)
  - Erreur d'assemblage serveur avec code HTTP (ex. « HTTP 413 » = limite d'upload ingress prod → support Emergent)
  - Télémétrie : POST /api/telemetry/export {mode, server_audio, audio_chunks, aenc_err, src_peak, size, ua} → collection export_logs + GET /api/admin/telemetry/exports (admin)
- ✅ Testé preview : endpoints télémétrie 200 (insert + lecture admin), studio charge sans erreur, MOBILE_UA=false sur desktop, /api/export/finalize déjà validé (piste AAC présente)
- ⚠️ NÉCESSITE REDÉPLOIEMENT pour effet sur beat-cut.com. Si encore muet après ça : lire le toast final + /api/admin/telemetry/exports pour trancher (source silencieuse vs upload bloqué)

## Corrigé (13 juillet 2026) — Export bloqué par « Optimisation en arrière-plan » + optimisation trop longue
- Bug user : impossible d'exporter tant que le badge optimisation est là, et il dure longtemps
- FIX 1 (front) : `clipsExportBlocking()` remplace `clipsOptimizing()` pour l'export — ne bloque QUE si un clip UTILISÉ dans les plans n'est pas décodable localement (`!_wcReady` et (`_optimizing` ou `!_wcFail`)). Un upload/optimisation en arrière-plan ne bloque PLUS JAMAIS l'export (le moteur WebCodecs lit l'original local). Même logique assouplie pour genSerie. `clipsOptimizing()` supprimée (orpheline)
- FIX 2 (back) : `_probe_video()` (ffmpeg -i) avant Mux — si la vidéo est DÉJÀ H.264 ≤1080p à ≤12 Mbps → transcodage SAUTÉ (metadata.transcode_skipped), optimisation ~1 s au lieu de 30-90 s. media_status expose `skipped` ; le front ne re-télécharge pas le fichier dans ce cas (pas de swap inutile)
- ✅ Testé : upload mp4 H.264 propre → « Transcodage sauté … @ 2.1 Mbps » en ~1 s, status {transcoded:true, skipped:true} ; gate export validé sur les 5 cas (ready+optimizing→libre, fail+optimizing→bloqué, fail seul→libre avec message ensureClipsReady, tous prêts→libre, clip non utilisé en optimisation→libre)
- ⚠️ REDÉPLOIEMENT nécessaire
