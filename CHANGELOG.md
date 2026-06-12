# Changelog

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
