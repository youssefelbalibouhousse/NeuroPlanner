# Journal des modifications

Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/) ;
le projet suit le [versionnage sémantique](https://semver.org/lang/fr/).

## [1.0.0] — 2026-11-14

### Ajouté

- Plan d'apprentissage Lundi → Samedi : 4 blocs horaires, 5 piliers, 5 h par jour.
- Checklists interactives avec persistance immédiate en JSON.
- Minuteurs Focus 45 / Pause 10 / Feuille blanche 3 (démarrer, pause, reset, bip).
- Graphique Matplotlib de complétion par pilier, avec code couleur de refocalisation.
- Réinitialisation de la semaine avec confirmation.
- Navigation clavier `Ctrl+1` … `Ctrl+6`.
- Icône et logo générés (`tools/make_icon.py`).

### Technique

- Code restructuré en package `neuroplanner/` (couches `data`, `services`, `ui`).
- Minuteur extrait dans `services/countdown.py`, testable avec une horloge simulée.
- Persistance atomique avec quarantaine des fichiers illisibles.
- 113 tests (dont tests d'intégration GUI) et configuration Ruff / Pytest.
- Intégration continue GitHub Actions (lint + tests sans écran).
