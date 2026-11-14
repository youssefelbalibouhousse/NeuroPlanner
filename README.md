# NeuroPlanner

**Suivi d'un rythme d'apprentissage intensif (5 h / jour) fondé sur les principes de neuroplasticité.**

Application de bureau Python : navigation par jour, checklists persistées, minuteurs
d'encodage/consolidation/récupération, graphique de refocalisation par pilier — et un
**planning entièrement modifiable** (domaines, tâches, durées).

![Aperçu de NeuroPlanner](docs/screenshot.png)

---

## Principes pédagogiques

| Principe | Traduction dans l'app |
|---|---|
| **Répétition espacée** | Un rappel actif de la veille ouvre chaque journée ; 6 jours couvrant les piliers. |
| **Récupération active** | Minuteur « Feuille blanche 3 min » et tâche de restitution libre en fin de bloc. |
| **Gestion de la charge cognitive** | Blocs de 1 h 15 / 1 h 30, un seul objectif par bloc, minuteur Focus 45 min. |

## Fonctionnalités

- **Navigation Lundi → Samedi**, 4 blocs horaires par jour (07:30 → 14:30), 5 h au total.
- **Checklists interactives** : chaque coche est écrite immédiatement sur disque.
- **Domaines d'apprentissage modifiables** : ajouter, renommer, recolorer, supprimer un
  pilier (la suppression retire ses tâches après confirmation).
- **Tâches modifiables** : ajout (`+` sur un bloc), édition et suppression (`✎` sur une
  ligne), avec contrôle du pilier et de la durée.
- **Statistiques en direct** : avancement du jour, de la semaine, par pilier.
- **Minuteurs** : Focus 45, Pause 10, Feuille blanche 3 ; Démarrer / Pause / Reset, bip de fin.
- **Graphique de refocalisation** (Matplotlib) : rouge < 50 %, orange 50–79 %, vert ≥ 80 %,
  gris « vide » pour un pilier encore sans tâche.
- **Réinitialisation de la semaine** avec confirmation (les statistiques de focus sont conservées).
- **Raccourcis** `Ctrl+1` … `Ctrl+6` pour changer de jour.

| Gestion des domaines | Édition d'une tâche |
|---|---|
| ![Domaines](docs/dialog_domains.png) | ![Tâche](docs/dialog_task.png) |

## Installation

Python **3.10+** requis.

```powershell
git clone https://github.com/youssefelbalibouhousse/NeuroPlanner.git
cd NeuroPlanner

python -m venv .venv
.venv\Scripts\Activate.ps1        # macOS / Linux : source .venv/bin/activate

pip install -e .
python main.py
```

Sans installation (les dépendances étant présentes) :

```powershell
pip install customtkinter matplotlib
python main.py
```

### Lancement

| Commande | Effet |
|---|---|
| `python main.py` | lance l'application |
| `python -m neuroplanner` | identique, via le module |
| `neuroplanner` / `neuroplanner-gui` | commandes installées par `pip install -e .` (la variante GUI n'ouvre pas de console sous Windows) |
| `python -m neuroplanner --data-file .\progression.json` | utilise un fichier de progression précis (le plan est créé à côté) |
| `python -m neuroplanner --plan-file .\mon_plan.json` | utilise un planning précis |

## Où sont mes données ?

Deux fichiers JSON distincts, écrits automatiquement :

| Fichier | Contenu |
|---|---|
| `neuro_progress.json` | cases cochées + statistiques (sessions, temps de focus) |
| `neuro_plan.json` | domaines, blocs horaires et tâches (le planning) |

Emplacements :

- Windows : `%APPDATA%\NeuroPlanner\`
- macOS : `~/Library/Application Support/NeuroPlanner/`
- Linux : `~/.local/share/NeuroPlanner/`

Surcharges : `--data-file`, `--plan-file`, ou les variables `NEUROPLANNER_DATA` et
`NEUROPLANNER_PLAN`. Ces fichiers ne sont jamais versionnés (voir `.gitignore`).

```json
{
  "version": 1,
  "domains": [{ "name": "Dev & Archi", "color": "#7C9CFF" }],
  "days": {
    "lun": [
      {
        "start": "07:30", "end": "08:45",
        "title": "Dev & Archi", "intent": "Encodage profond",
        "tasks": [
          { "id": "lun-0-0", "label": "Architecture hexagonale…", "domain": "Dev & Archi", "minutes": 45 }
        ]
      }
    ]
  }
}
```

L'écriture est atomique (fichier temporaire + `os.replace`) : une coupure ne peut
pas laisser un JSON tronqué. Un fichier illisible est mis de côté en
`*.corrupt.json` plutôt que d'être écrasé, et les identifiants de tâches inconnus
sont ignorés au chargement.

## Structure du projet

```text
NeuroPlanner/
├── main.py                     # point d'entrée pratique
├── pyproject.toml              # métadonnées, dépendances, ruff, pytest
├── neuroplanner/
│   ├── app.py                  # fenêtre principale (orchestration)
│   ├── config.py               # jours, chemins, version
│   ├── formatting.py           # formats (durées, dates, pourcentages)
│   ├── models.py               # modèles immuables (Task, Block, DayPlan, Domain…)
│   ├── theme.py                # palette, couleurs par domaine, polices
│   ├── data/
│   │   ├── curriculum.py       # programme par défaut (graine du plan)
│   │   ├── plan_store.py       # planning modifiable persisté
│   │   ├── presets.py          # préréglages des minuteurs
│   │   ├── store.py            # progression persistée
│   │   └── jsonfile.py         # lecture/écriture JSON atomique
│   ├── services/
│   │   ├── countdown.py        # minuteur pur (testable sans écran)
│   │   ├── stats.py            # agrégations de progression
│   │   └── sound.py            # signal sonore de fin
│   ├── ui/                     # sidebar, day_view, block_card, task_row,
│   │                           # timer_panel, chart, header, dialogs, widgets
│   └── assets/                 # icône et logo
├── tests/                      # 179 tests (dont intégration GUI)
├── docs/ARCHITECTURE.md        # modules, format du plan, branchement d'un LLM
└── tools/make_icon.py          # régénère l'icône
```

Détail des responsabilités, format du plan et recettes de modification :
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Personnaliser

Depuis l'interface, sans toucher au code :

- **Domaines** → bouton « Domaines… » de la barre latérale.
- **Tâches** → `+` dans l'en-tête d'un bloc, `✎` sur une ligne existante.
- **Couleur d'un domaine** → clic sur sa pastille (rotation dans la palette).

Dans le code :

- **Programme par défaut** → `neuroplanner/data/curriculum.py` (graine du premier lancement).
- **Minuteurs** → `neuroplanner/data/presets.py`.
- **Palette sombre** → `neuroplanner/theme.py` (`Palette`, `DOMAIN_PALETTE`).
- **Seuils de refocalisation** → `REFOCUS_BELOW` / `MASTERY_FROM` dans
  `neuroplanner/services/stats.py`.

## Développement

```powershell
pip install -e ".[dev]"

python -m ruff check .            # lint
python -m pytest                  # tous les tests (ouvre des fenêtres)
python -m pytest -m "not gui"     # tests sans écran (CI)
python -m pytest --cov=neuroplanner --cov-report=term-missing
```

Les tests d'interface sont marqués `gui` : ils construisent une vraie fenêtre Tk
avec des fichiers temporaires, cochent des tâches, changent de jour, éditent le
plan via les dialogues et font tourner un minuteur accéléré.

## Feuille de route

- [x] Planning modifiable : domaines, tâches, durées.
- [ ] **Génération du planning par un LLM gratuit** (chapitre par chapitre) : le plan
      est déjà un document JSON stable et `PlanStore.replace_week()` est le point
      d'entrée prévu — voir
      [la feuille de route détaillée](docs/ARCHITECTURE.md#brancher-un-llm-feuille-de-route).
- [ ] Historique multi-semaines et courbe de rétention.
- [ ] Thème clair commutable et export CSV.
- [ ] Packaging `PyInstaller` (exécutable Windows autonome).

## Licence

[MIT](LICENSE)
