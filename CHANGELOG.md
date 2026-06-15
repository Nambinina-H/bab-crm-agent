# Changelog

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
