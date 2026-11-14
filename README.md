# NeuroPlanner

**Suivi d'un rythme d'apprentissage intensif (5 h / jour) fondé sur les principes de neuroplasticité.**

Application de bureau Python : navigation par jour, checklists persistées, minuteurs
d'encodage/consolidation/récupération et graphique de refocalisation par pilier.

![Aperçu de NeuroPlanner](docs/screenshot.png)

---

## Principes pédagogiques

| Principe | Traduction dans l'app |
|---|---|
| **Répétition espacée** | Un rappel actif de la veille ouvre chaque journée ; 6 jours couvrant 5 piliers. |
| **Récupération active** | Minuteur « Feuille blanche 3 min » et tâche de restitution libre en fin de bloc. |
| **Gestion de la charge cognitive** | Blocs de 1 h 15 / 1 h 30, un seul objectif par bloc, minuteur Focus 45 min. |

## Fonctionnalités

- **Navigation Lundi → Samedi**, 4 blocs horaires par jour (07:30 → 14:30), 5 h au total.
- **Checklists interactives** : chaque coche est écrite immédiatement sur disque.
- **Statistiques en direct** : avancement du jour, de la semaine, par pilier.
- **Minuteurs** : Focus 45, Pause 10, Feuille blanche 3 ; Démarrer / Pause / Reset, bip de fin.
- **Graphique de refocalisation** (Matplotlib) : rouge < 50 %, orange 50–79 %, vert ≥ 80 %.
- **Réinitialisation de la semaine** avec confirmation (les statistiques de focus sont conservées).
- **Raccourcis** `Ctrl+1` … `Ctrl+6` pour changer de jour.

## Installation

Python **3.10+** requis.

```powershell
git clone https://github.com/<votre-compte>/NeuroPlanner.git
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
| `python -m neuroplanner --data-file .\ma_progression.json` | utilise un fichier de progression précis |

## Où sont mes données ?

La progression est un fichier JSON écrit automatiquement :

- Windows : `%APPDATA%\NeuroPlanner\neuro_progress.json`
- macOS : `~/Library/Application Support/NeuroPlanner/neuro_progress.json`
- Linux : `~/.local/share/NeuroPlanner/neuro_progress.json`

Surcharges possibles : `--data-file CHEMIN` ou la variable d'environnement
`NEUROPLANNER_DATA`. Le fichier n'est jamais versionné (voir `.gitignore`).

Format :

```json
{
  "version": 1,
  "updated_at": "2026-11-14T23:41:00",
  "completed": { "lun-0-0": true },
  "stats": { "sessions": 4, "focus_seconds": 10800 }
}
```

L'écriture est atomique (fichier temporaire + `os.replace`) : une coupure ne peut
pas laisser un JSON tronqué. Un fichier illisible est mis de côté en
`neuro_progress.corrupt.json` plutôt que d'être écrasé.

## Structure du projet

```text
NeuroPlanner/
├── main.py                     # point d'entrée pratique
├── pyproject.toml              # métadonnées, dépendances, ruff, pytest
├── neuroplanner/
│   ├── app.py                  # fenêtre principale (orchestration)
│   ├── config.py               # jours, chemins, version
│   ├── formatting.py           # formats (durées, dates, pourcentages)
│   ├── models.py               # modèles immuables (Task, Block, DayPlan…)
│   ├── theme.py                # palette, couleurs par pilier, polices
│   ├── data/
│   │   ├── curriculum.py       # ← le plan de la semaine (à personnaliser)
│   │   ├── presets.py          # préréglages des minuteurs
│   │   └── store.py            # persistance JSON
│   ├── services/
│   │   ├── countdown.py        # minuteur pur (testable sans écran)
│   │   ├── stats.py            # agrégations de progression
│   │   └── sound.py            # signal sonore de fin
│   ├── ui/                     # sidebar, day_view, block_card, task_row,
│   │                           # timer_panel, chart, header, widgets
│   └── assets/                 # icône et logo
├── tests/                      # 113 tests (dont tests d'intégration GUI)
├── docs/ARCHITECTURE.md        # guide des modules et recettes de modification
└── tools/make_icon.py          # régénère l'icône
```

Détail des responsabilités et scénarios de modification :
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Personnaliser

- **Le programme** → `neuroplanner/data/curriculum.py`, fonction `_day(...)` de chaque
  jour : libellés, piliers et durées. Les identifiants, statistiques et le
  graphique se recalculent seuls.
- **Les minuteurs** → `neuroplanner/data/presets.py`.
- **Les couleurs** → `neuroplanner/theme.py` (`Palette`, `DOMAIN_COLORS`).
- **Les seuils de refocalisation** → `REFOCUS_BELOW` / `MASTERY_FROM` dans
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
avec un fichier de données temporaire, cochent des tâches, changent de jour et
font tourner un minuteur accéléré.

## Feuille de route

- [ ] Thème clair commutable et export des statistiques (CSV).
- [ ] Historique multi-semaines et courbe de rétention.
- [ ] Édition du programme depuis l'interface.
- [ ] Packaging `PyInstaller` (exécutable Windows autonome).

## Licence

[MIT](LICENSE)
