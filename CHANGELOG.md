# Journal des modifications

Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/) ;
le projet suit le [versionnage sémantique](https://semver.org/lang/fr/).

## [1.3.4] — 2026-11-15

### Corrigé

- **Barre latérale inaccessible en bas** : sur un écran bas (fenêtre de 466 px
  logiques), les boutons « Importer un programme… », « Domaines… » et
  « Réinitialiser la semaine » sortaient de la fenêtre et restaient inatteignables.
  La barre est désormais scindée en deux zones :
  - `Sidebar.body` (défilante) : marque, les 6 jours et la carte « PROGRESSION » ;
  - `Sidebar.footer` (ancrée en bas) : les trois actions et le rappel des
    raccourcis, **toujours visibles**, sans rien faire défiler.
  Sur un grand écran, tout tient sans défilement ; sur un écran bas, la molette
  atteint les jours suivants et le résumé.
- 329 tests (+2) : actions hors de la zone défilante en fenêtre courte, dernier
  jour et résumé atteignables après défilement.

## [1.3.3] — 2026-11-15

### Ajouté

- `tools/create_shortcut.ps1` : crée les raccourcis **Bureau + menu Démarrer** avec
  l'icône du paquet et sans fenêtre de console (lanceur `neuroplanner-gui.exe`,
  avec repli sur `pythonw -m neuroplanner`). Idempotent, `-Python` pour viser un
  interpréteur précis, `-NoStartMenu` pour le Bureau seul.

### Documentation

- README : section « Icône sur le Bureau » et explication de ce qu'apporte — ou
  non — un `.exe` autonome (PyInstaller), à réserver au partage de l'app.
- Exemple `--check-llm` mis à jour (modèles Groq actuels, ligne `Note`).

## [1.3.2] — 2026-11-15

### Corrigé

- **Échec de génération chez Groq (`HTTP 404 model_not_found`) alors que la clé
  fonctionnait** : le modèle mémorisé (`llama-3.3-70b-versatile`) avait été retiré
  du catalogue. Deux corrections :
  - le menu des modèles n'affiche plus que la liste réelle du fournisseur ; les
    suggestions du registre ne sont plus réinjectées par-dessus (elles
    réintroduisaient le modèle disparu et le laissaient sélectionné) ;
  - si la génération échoue pour un modèle absent, le client bascule **une seule
    fois** sur le meilleur modèle accessible (préférence du registre, puis ordre de
    l'API) et le dialogue indique `modèle <nom>` dans son état. Sans repli possible,
    l'erreur énumère les modèles disponibles avec la clé.
- Les modèles non conversationnels (`whisper`, `orpheus`, `prompt-guard`,
  `safeguard`, `embed`…) sont écartés des listes : les proposer garantissait un
  échec.
- `--check-llm` signale un modèle mémorisé qui n'existe plus (ligne `Note`, repli
  annoncé) au lieu de le présenter comme valide ; côté Ollama, il rappelle la
  commande `ollama pull` à lancer.
- Modèles Groq suggérés mis à jour (`openai/gpt-oss-120b`, `openai/gpt-oss-20b`,
  `qwen/qwen3.8-27b`).

### Ajouté

- 327 tests (+18) : filtrage des modèles de chat, détection d'un modèle retiré,
  bascule automatique, absence de nouvelle tentative sur une erreur d'authentification,
  absence de fusion des suggestions, avertissement du diagnostic.

## [1.3.1] — 2026-11-15

### Corrigé

- **Groq était inutilisable** : l'API (derrière Cloudflare) répondait
  `403 error code: 1010` au User-Agent par défaut d'`urllib`. Toutes les requêtes
  envoient désormais `User-Agent: NeuroPlanner/<version>` ; un test verrouille ce
  comportement.
- Gemini renvoie `400 « Please pass a valid API key »` pour une clé absente ou
  invalide : le message affiche maintenant « Clé refusée ou invalide » au lieu de
  suggérer un problème de modèle.
- `--provider X` sans `--model` reprend le modèle par défaut du fournisseur, et non
  celui du fournisseur précédent.

### Ajouté

- `--check-llm` : diagnostic en une commande (URL, clé masquée, liste des modèles),
  sans interface, sans jeton consommé, code de sortie `0`/`1`.
- `models(strict=True)` sur les deux clients : le diagnostic remonte l'erreur au lieu
  d'une liste vide.
- 308 tests (+7).

## [1.3.0] — 2026-11-15

### Ajouté

- **Fournisseurs hébergés à palier gratuit** : Groq, Gemini et Mistral, derrière le
  même contrat que le modèle local. Un seul client (`OpenAiCompatClient`) suffit,
  les trois exposant une API `chat/completions` compatible OpenAI.
- Registre de fournisseurs (`services/providers.py`) : ajouter un fournisseur =
  ajouter une entrée (URL de base, variable d'environnement, modèles suggérés).
- Sélecteur de fournisseur et champ de clé masqué dans le dialogue d'import ;
  liste des modèles récupérée auprès du fournisseur quand la clé est valide.
- Mémorisation optionnelle du fournisseur et de la clé dans `llm_settings.json`
  (hors dépôt, `0600` là où POSIX le permet), ou via variables d'environnement.
- Erreurs traduites et actionnables : clé refusée (401/403), modèle introuvable
  (404), quota atteint (429), service indisponible (5xx), serveur injoignable.
- **Redaction** : la clé n'apparaît jamais dans un message d'erreur, même si l'API
  la renvoie dans son corps de réponse.

### Modifié

- `LlmSettings` porte désormais `provider` et `api_key` ; `resolve_settings()`
  applique l'ordre fichier local > variables d'environnement > défauts.
- `generate_outline()` instancie le bon client via `providers.create_client()`.
- Transport HTTP unifié : `(url, payload, headers, timeout)`, partagé par les deux
  clients et mockable dans les tests.

### Technique

- 297 tests (dont 56 sur les fournisseurs, les réglages et le dialogue d'import) ;
  aucun test ne contacte le réseau.

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
