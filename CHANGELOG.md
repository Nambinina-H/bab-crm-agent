# Changelog

## 1.1.0
**Changed**
- **Refonte de l'interface** (style plat teal/navy, sans coins arrondis) : la
  navigation passe par des **onglets** en haut (**Accueil / Profil / Paramètres**)
  au lieu du menu ; statut avec **pastille + texte colorés** selon l'état ;
  boutons **Play / Pause / Stop** de largeur égale, celui de l'état courant
  **rempli** de sa couleur (Play vert / Pause orange) ; champs en lecture seule
  sur fond gris. **Aucun changement de comportement.**
- Champ **« Projet »** (ex-« Nom de la vidéo »).
- Bouton **Pause** : icône dessinée (deux barres serrées) au lieu d'un glyphe de
  police (rendu net et stable).

**Added**
- **Démarrage automatique** (onglet **Paramètres**) : une case à cocher
  « Redémarrage automatique » qui ouvre l'agent **à l'ouverture de session
  Windows** (clé `HKCU\\…\\Run`, sans droits admin). Utile après une coupure de
  courant ou un redémarrage. Réglage par utilisateur, activable/désactivable.
- Rôle **« Stagiaire »** ajouté à la liste des rôles.

## 1.0.9
**Added**
- **Rappel de mise à jour bien visible** dans le timer flottant (toujours au-dessus
  de l'écran) : en **Play/Pause**, le compteur reste et le rappel s'affiche
  **dessous** ; **à l'arrêt**, le rappel **remplace** le compteur. **Cliquer** le
  rappel **redémarre** l'app pour appliquer la MAJ.
- **Auto-application de la MAJ à l'arrêt** : si une mise à jour est prête et que
  l'agent reste **à l'arrêt** quelques minutes, il se met à jour **tout seul**
  (les postes « juste ouverts » n'ont plus besoin d'action). Un agent en
  **Play/Pause n'est jamais coupé** (il voit seulement le rappel).
- **Rôle dans Paramètres** : un menu déroulant **Rôle** (sous Nom) lié au champ
  rôle de la plateforme (page Collaborateurs) ; il affiche le rôle courant et le
  met à jour côté serveur à l'enregistrement. Rôles ajoutés : **Informaticien**,
  **IA**.
- **Numéros de priorité dans la liste des projets** : la liste déroulante affiche
  « 1. … », « 2. … » selon l'ordre défini par le manager (le n°1 reste
  pré-sélectionné à l'ouverture).

**Fixed**
- **Bouton « Redémarrer »** : le redémarrage est désormais **fiable** (relanceur
  qui attend la fin du process — compatible avec le verrou mono-instance) et
  fonctionne **aussi en développement** (relance `python -m app.main`).

**Interne**
- `AGENT_FAKE_UPDATE=1` : force « mise à jour prête » en local pour **tester** le
  bandeau / le rappel / le redémarrage sans build.

## 1.0.8
**Changed**
- **Identité par personne (nom@PC)** : l'identité d'un collaborateur est désormais
  basée sur **son nom** (et le PC), plus sur l'utilisateur Windows. Conséquences :
  - Quand un **autre collaborateur** prend le poste, il suffit de changer le nom
    dans Paramètres → l'agent bascule sur une **nouvelle identité** ; l'historique
    de l'ancien **reste sous son nom** (fini le mélange Omar → Nicolas).
  - **Insensible à la casse** (« Omar » = « omar »).
  - **Revenir à un ancien nom** sur le poste **retrouve ses données**.
  - **Migration transparente** au 1ᵉʳ lancement : l'ancien identifiant machine est
    renommé en `nom@PC` côté serveur (les données suivent, **aucune perte**).
**Added**
- **Priorisation des projets** : les projets assignes s'affichent dans l'**ordre de
  priorite** defini par le manager (le n°1 est **pre-selectionne** a l'ouverture) ;
  un marqueur « ★ Priorité n°X » indique le rang du projet selectionne. L'ordre
  vient du serveur (aucune action requise sur le poste).

**Changed**
- **Compteur cale sur le serveur** : le temps affiche suit desormais le total du
  serveur (= le dashboard) au lieu du seul buffer local, plus le temps du segment
  en cours. Fini les ecarts agent/plateforme. Hors-ligne, le calcul local prend
  le relais (rien n'est fige ni perdu) et tout se realigne a la reconnexion.
- **Reset unique du buffer local** (une seule fois apres cette MAJ, des que le
  serveur est joignable) : les segments **deja envoyes** sont purges pour repartir
  proprement du serveur ; les segments **en attente sont conserves** (aucune
  perte). Nettoie d'eventuels doublons locaux herites de l'ere pre-verrou.

**Fixed**
- **Verrou mono-instance** : impossible de lancer deux agents en meme temps sur
  le meme poste/session. Deux instances simultanees capturaient l'activite **en
  double** (segments en doublon decales de quelques microsecondes, que la
  deduplication serveur ne voit pas) -> le temps affiche cote plateforme etait
  **gonfle** (un projet pouvait apparaitre « depasse » a tort). Si l'agent est
  deja ouvert, un message le signale et la 2e fenetre se ferme. Sans impact sur
  la mise a jour automatique (qui attend deja la fermeture de l'ancien .exe avant
  de relancer le nouveau).

## 1.0.6
**Added**
- **Marquer un projet terminé depuis l'agent** : un bouton « ✓ Marquer ce projet
  terminé » (mode projets assignes) permet au monteur de signaler un livrable
  fini. Le projet passe « terminé » cote plateforme et **sort de sa liste**
  (le suivi en cours est arrete). Action distincte de Play/Pause/Stop.

**Changed**
- **Synchro des projets assignes plus reactive (~5 s** au lieu de 20 s) : les
  changements cote serveur (assignation, terminer/rouvrir) apparaissent plus
  vite dans l'agent.
- **Vocabulaire** : « Monteur » -> « **Collaborateur** » dans l'agent.
- **Parametres** : champ « Nom du monteur » -> « **Nom** ».

## 1.0.5
**Fixed**
- **Mise a jour fiable** : l'agent verifie desormais que le fichier telecharge est
  **complet** (taille exacte annoncee par GitHub) et **valide** (vrai .exe) AVANT
  de l'installer. Evite d'appliquer une MAJ corrompue/tronquee qui provoquait
  l'erreur « Failed to load Python DLL ... python312.dll » au demarrage.

## 1.0.4
**Added**
- **Version remontee au dashboard** : l'agent joint sa version a chaque heartbeat ;
  la plateforme affiche la version installee sur chaque poste (Parametres ->
  « Versions des agents »). Additif, sans impact sur le reste.

## 1.0.3
**Added**
- **APM (clics / minute)** : l'agent compte les clics souris (boutons
  gauche/droit/milieu) et les rattache au segment en cours ; la plateforme
  affiche un APM par collaborateur = clics / minutes actives. Indicateur
  d'**intensite d'interaction** (pas un score de productivite), distinct du
  taux d'activite. Comptage par sondage leger (`GetAsyncKeyState`), **sans
  hook ni injection** (profil antivirus quasi nul) ; **jamais le clavier**,
  jamais de contenu de frappe (uniquement un nombre). Entierement additif :
  l'actif/inactif, le taux et les heures sont inchanges ; un ancien agent qui
  n'envoie pas de clics est traite comme 0.
- **Mise a jour immediate depuis le dashboard** : un bouton « Mettre a jour tous
  les agents maintenant » (Parametres) declenche le telechargement sur tous les
  agents ouverts en ~1 min (au lieu d'attendre la verification automatique de
  30 min) ; la notif « Redemarrer » s'affiche ensuite. La verif periodique
  reste le filet de secours.

**Changed**
- **Timer flottant** : suppression du clignotement (zoom avant/arriere) quand le
  projet est depasse ; le temps reste simplement affiche en rouge.

**Fixed**
- **Icone de l'application** : l'.exe porte desormais le logo BAB CRM (barre des
  taches / Explorateur) au lieu de l'icone Python generique.

## 1.0.0
**Added**
- Agent Windows (Tkinter) : pointage declaratif (client / video / version) valide
  par l'activite souris-clavier ; Play / Pause / Stop ; chrono cumulatif par
  livrable ; **temps restant** du projet (vert / orange / rouge + pulsation si depasse).
- Robustesse hors-ligne : buffer local SQLite, synchronisation en arriere-plan.
- Presence temps reel (heartbeat) + config centrale recuperee a chaud.
- **Enregistrement automatique** du monteur des la configuration du nom (visible
  et assignable cote plateforme sans attendre d'activite).
- **Projets assignes synchronises** automatiquement (creation / modification /
  suppression refletees dans l'agent).
- **Mise a jour automatique** via les Releases GitHub (telechargement en arriere-plan,
  installation au prochain demarrage ; la config du poste est conservee).
- **Timer flottant** verrouille en haut a droite de l'ecran (toujours visible
  jusqu'a la fermeture de l'app) ; le chrono n'est plus dans la fenetre, il vit
  uniquement dans ce bandeau.
- Application **BABCRM - agent** (nom de l'.exe + de la fenetre) ; logo BAB CRM.
- **Heure d'activite fiable** : l'agent transmet son heure UTC a l'envoi
  (`client_sent_at`) pour que le serveur recale ses horodatages si l'horloge du
  poste est decalee (les heures ne dependent plus de l'horloge du PC).
- **Presence "en ligne" des l'ouverture** : agent ouvert = en ligne (connecte),
  meme sans Play (etat `online`, sans activite). Le suivi du temps reste
  exclusivement lie au Play (aucun segment cree sans Play). Hors-ligne envoye
  uniquement a la fermeture.
- **Mise a jour plus reactive** : verification des Releases au demarrage puis
  toutes les **30 min** (au lieu de 6 h).
- **Publication automatisee** (GitHub Action `.github/workflows/release.yml`) :
  pousser un tag `vX.Y.Z` builde l'.exe et publie la Release (version
  synchronisee sur le tag) -> les agents se mettent a jour seuls.
- **Bandeau de notification in-app** (reutilisable) : quand une nouvelle version
  est telechargee, un bandeau "Une nouvelle version est prete" + bouton
  **Redemarrer** propose d'appliquer la MAJ immediatement (sinon elle s'applique
  au prochain demarrage).
- **Config injectee au build (URL + cle API)** : l'.exe publie par la CI marche
  **sans .env** (valeurs lues depuis les Secrets GitHub, jamais committees). Un
  `.env` local reste prioritaire au runtime (tests / serveur de staging).

**Interne**
- Decoupage de l'UI (`app_window.py` monolithe) en composants `ui/` : `theme`
  (constantes), `notification` (bandeau reutilisable), `floating_timer`
  (overlay) ; `app_window` devient l'orchestrateur. Iso-comportement.
