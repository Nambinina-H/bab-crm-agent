# BAB CRM — Agent (poste Windows)

Programme qui tourne sur le PC de chaque monteur avec une **petite fenetre de
controle**. L'employe saisit son **nom** et son **projet**, puis clique **Play** :
l'agent mesure alors l'**application au premier plan**, le **titre de la fenetre**
et l'etat **actif / inactif** (souris/clavier). Il peut **Pause** (le temps de
pause est comptabilise) ou **Stop**.

C'est donc un **pointage declaratif** (le projet est choisi par l'employe, pas
devine) **valide par l'activite** souris/clavier.

**Vie privee : aucune capture d'ecran, aucun keylogger.** Seuls le nom de l'app,
le titre de la fenetre et l'etat (actif / inactif / pause) sont enregistres — et
**rien n'est mesure tant que l'employe n'a pas clique Play**.

> Le serveur est un projet separe (son propre depot). L'agent lui parle
> uniquement par HTTP (`AGENT_SERVER_URL`).

---

## Robustesse (hors-ligne)

L'agent ecrit **d'abord en local** (`local_buffer.db`), puis tente d'envoyer. Si
le reseau est coupe, rien n'est perdu : les mesures partent des que la connexion
revient. Un thread de synchronisation s'en occupe en arriere-plan.

---

## 1. Installation (test)

Prerequis : **Python 3.10+** (l'agent est concu pour **Windows**).

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Configuration

La config est separee en deux : les **secrets** dans `.env`, le **reglage** dans
`config.json`.

### Secrets — `.env`

Cree un fichier `.env` a la racine de l'agent (il n'est jamais versionne) :

```bash
AGENT_API_KEY=la-meme-cle-que-le-serveur
AGENT_SERVER_URL=http://localhost:8000
```

| Variable | Role |
|---|---|
| `AGENT_API_KEY` | Cle partagee : **identique** au `AGENT_API_KEY` du serveur |
| `AGENT_SERVER_URL` | Adresse du serveur (ex. `http://localhost:8000`, ou `https://...`) |

### Reglages — `config.json`

`config.json` est **fourni et versionne** (il ne contient aucun secret). Edite-le
directement pour ajuster les reglages :

| Champ | Role | Defaut |
|---|---|---|
| `sample_interval_sec` | Frequence de mesure (s) | 5 |
| `idle_threshold_sec` | Sans activite au-dela -> etat « inactif » (s) | 120 |
| `auto_pause_threshold_sec` | Inactivite prolongee -> auto-pause (s ; `0` = desactive) | 300 |
| `sync_interval_sec` | Frequence d'envoi au serveur (s) | 60 |
| `sync_batch_size` | Nb max d'evenements par envoi | 500 |

> **Identite** : le **nom** est saisi dans la fenetre (libelle affiche) ; la cle
> technique stable est l'`employee_id` base sur la machine (`utilisateur@nom-du-pc`,
> automatique) — pas besoin de le configurer.

> Priorite : variable d'environnement > `.env` > `config.json` > defaut.
> Seul `.env` (les secrets) est exclu du versionnement ; `config.json` est suivi.

### L'interface (utilisation)

Au lancement, une fenetre s'ouvre en etat **Arrete**. L'employe renseigne :

- **Nom** (l'employe),
- **Client**,
- **Nom de la video** (avec autocompletion des videos deja saisies),
- **Version** (liste V1, V2, ... ou saisie libre),

puis :

1. clique **▶ Play** -> la mesure demarre (minuteur = temps travaille depuis le Play, pauses deduites),
2. **⏸ Pause** quand il s'arrete (le temps de pause est enregistre), **▶ Play** pour reprendre,
3. **⏹ Stop** en fin de session.

Changer le **client / la video / la version** en cours de session est possible :
la mesure bascule aussitot sur le nouveau contexte. En cas d'inactivite
prolongee, l'agent passe **automatiquement en pause**.

## 3. Lancement

```bash
python -m app.main
```

> Bien `python -m app.main` (et **pas** `python app\main.py`, qui plante a cause
> des imports en paquet).

---

## 4. Deploiement sur les postes

### Un .exe autonome (PyInstaller)

Pour ne rien installer sur les postes, fabrique un executable unique (une fois,
sur une machine Windows) :

```bash
pip install pyinstaller

# 1) (une fois) generer l'icone .ico multi-tailles depuis le logo, ex. avec
#    ImageMagick (ou un convertisseur PNG -> ICO en ligne) :
magick assets\logo.png -define icon:auto-resize=256,48,32,16 assets\lcsify.ico

# 2) builder depuis le dossier agent/ :
#    --paths .             resout les imports "app.*"
#    --icon                icone du .exe
#    --add-data            embarque le logo affiche dans la fenetre
pyinstaller --onefile --noconsole --name LCSify --paths . ^
  --icon assets\lcsify.ico --add-data "assets;assets" app\main.py
```

Tu obtiens `dist/LCSify.exe`. Copie-le sur chaque poste **avec** son
`.env` et son `config.json` dans le meme dossier (le logo, lui, est deja
embarque dans le `.exe`).

### Demarrage automatique a l'ouverture de session

Via le Planificateur de taches Windows (en admin) :

```bat
schtasks /create /tn "LCSify" /tr "C:\LCSify\LCSify.exe" ^
  /sc onlogon /rl highest /f
```

---

## 5. Qualite du code (pre-commit)

Hooks : `ruff` (lint), `gitleaks` (secrets), espaces de fin, YAML, tri imports.

```bash
git init                          # si pas deja un depot git
pip install -r requirements.txt   # inclut ruff + pre-commit
pre-commit install
pre-commit run --all-files        # controle complet
```

Sans git, le lint seul fonctionne : `ruff check app`.

---

## 6. Mise a jour automatique des agents

L'agent se met a jour **tout seul**, comme une appli mobile. La **config de chaque
poste est conservee** (`config.json`, `.env` vivent a cote de l'`.exe` et ne sont
jamais remplaces — seul le binaire l'est).

**Comment ca marche**
1. L'agent embarque sa version (`app/version.py`, ex. `1.0.0`).
2. En arriere-plan (au demarrage, puis toutes les ~6 h), il interroge la
   **derniere Release** du depot public et compare le tag a sa version.
3. Si une version plus recente existe, il **telecharge le nouvel `.exe`** a cote
   de l'actuel (`update.exe`), sans interrompre la session.
4. **Au prochain demarrage**, il installe la mise a jour (remplace l'`.exe` puis
   relance). Le monteur n'a rien a faire.

**Publier une nouvelle version (ce que TU fais)**
1. Incrementer la version dans [`app/version.py`](app/version.py) (ex. `1.0.1`).
2. Builder l'`.exe` : `pyinstaller --noconfirm LCSify.spec` -> `dist/LCSify.exe`.
3. Sur GitHub, creer une **Release** avec le tag **`v1.0.1`** (= la version) et
   y **joindre `dist/LCSify.exe`** en asset.
4. C'est tout : les agents detecteront `v1.0.1 > 1.0.x` et se mettront a jour.

> Le tag doit etre **superieur** a la version installee pour declencher la MAJ.
> Le depot doit rester **public** (telechargement sans authentification).

> **Important (1re fois)** : les `.exe` deja deployes ne contiennent pas encore
> ce mecanisme. Il faut distribuer **une fois** manuellement l'`.exe` qui l'inclut
> (version 1.0.0) ; ensuite tout est automatique.
