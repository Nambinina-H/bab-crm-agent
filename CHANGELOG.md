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
  jusqu'a la fermeture de l'app).
- Marque **BAB CRM** (nom de fenetre + logo).
