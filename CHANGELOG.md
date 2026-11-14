# Journal des modifications

Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/) ;
le projet suit le [versionnage sémantique](https://semver.org/lang/fr/).

## [1.2.0] — 2026-11-15

### Ajouté

- **Import d'un programme** : dialogue dédié (`Importer un programme…`) qui
  transforme une table des matières en planning complet, avec aperçu des 30 tâches
  avant application.
- **Assistant LLM local** (Ollama, gratuit et hors ligne) : le modèle propose les
  chapitres, l'application construit le planning (`services/generation.py`).
  Option « raisonnement étendu » (`think`) pour les modèles qui le supportent.
- `services/chapters.py` : parser tolérant (puces, numéros, `(90 min)`, `1 h 30`).
- `services/llm.py` : client Ollama sans dépendance (urllib), transport injectable,
  messages d'erreur actionnables (`ollama serve`, `ollama pull`), extraction JSON
  robuste aux raisonnements contenant des crochets.
- `PlanStore.replace_week(..., prune_unused_domains=True)` : un import peut ne
  conserver que les piliers réellement utilisés.
- Variables `NEUROPLANNER_OLLAMA_URL`, `NEUROPLANNER_LLM_MODEL`,
  `NEUROPLANNER_LLM_THINK`.
- Les boîtes modales sont bornées à l'écran (utile en 1280×720 à 150 %).

### Technique

- 260 tests (dont 39 d'intégration GUI sur l'édition et l'import) ; aucun test ne
  contacte le réseau : `OllamaClient` accepte un transport factice.

### Modifié

- `domain_progress` et le graphique gèrent les piliers vides (« vide » en gris).
- La version est exposée par `neuroplanner.__version__` et `--version`.

## [1.1.0] — 2026-11-14

### Ajouté

- **Gestion des domaines** : dialogue dédié pour ajouter, renommer, recolorer et
  supprimer un pilier d'apprentissage (confirmation indiquant le nombre de tâches
  supprimées, refus de supprimer le dernier domaine).
- **Édition des tâches** : bouton `+` dans chaque bloc pour créer une tâche,
  bouton `✎` sur chaque ligne pour la modifier ou la supprimer ; pilier et durée
  contrôlés (1 à 240 min), total du bloc affiché en direct.
- **Planning persisté** dans `neuro_plan.json`, distinct de la progression : le
  document devient la cible d'un futur générateur (LLM, import de chapitres).
- `PlanStore.replace_week()` : point d'entrée pour remplacer tout un programme.
- Option `--plan-file` et variable `NEUROPLANNER_PLAN`.
- Affichage « vide » (gris) dans le graphique pour un pilier encore sans tâche.
- Captures des dialogues dans `docs/` et section « Brancher un LLM » dans la
  documentation d'architecture.

### Modifié

- Les domaines ne sont plus figés dans le code : ils sont chargés depuis le plan,
  `curriculum.py` ne servant plus que de graine et de valeur de réinitialisation.
- `ProgressStore` filtre les identifiants inconnus via `valid_ids`, avec
  `prune()` / `forget()` pour purger les coches orphelines après édition du plan.
- Les identifiants des tâches créées sont stables (`t<8 hex>`) : éditer le plan ne
  décale plus les cases cochées.
- `domain_progress(order=...)` renvoie désormais aussi les piliers sans tâche.

### Technique

- Écriture JSON factorisée dans `data/jsonfile.py` (atomique, quarantaine).
- 179 tests (dont 35 d'intégration GUI sur l'édition du plan), Ruff et CI à jour.

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
