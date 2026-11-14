# Architecture

Document destiné à celui qui **modifie** le projet. Il décrit les couches, le flux
de données, le format du plan et les recettes pour les changements fréquents.

## Couches

```text
┌────────────────────────────────────────────────────────────────┐
│ ui/            widgets CustomTkinter (aucune décision métier)  │
│  sidebar  header  day_view  block_card  task_row               │
│  timer_panel  chart  dialogs  import_dialog  widgets           │
└──────────────▲────────────────────────────┬───────────────────┘
               │ callbacks                  │ lecture
┌──────────────┴────────────────────────────▼───────────────────┐
│ app.py       orchestration : jour courant, plan, progression   │
└──────▲────────────────────┬───────────────────────┬────────────┘
       │                    │                       │
┌──────┴───────────┐ ┌──────▼──────────┐ ┌──────────▼──────────┐
│ services/        │ │ data/           │ │ data/               │
│  stats  (purs)   │ │  plan_store     │ │  store              │
│  countdown (pur) │ │  curriculum     │ │  (progression)      │
│  chapters        │ │  presets        │ │  llm_config         │
│  generation      │ └─────────────────┘ │  jsonfile (E/S)     │
│  llm  providers  │                     └─────────────────────┘
│  sound           │
└──────▲───────────┘
       │
   ┌───┴───────────────────────────────────────────────────────┐
   │ models.py (dataclasses immuables, dont Chapter)           │
   └───────────────────────────────────────────────────────────┘
```

Règles de dépendance :

- `models.py` ne dépend de rien (sauf `__future__`).
- `services/stats.py` et `services/countdown.py` ignorent totalement Tk : ils
  manipulent des `models.*` et des nombres, donc se testent sans écran.
- `ui/` ne décide jamais de l'état : il affiche et remonte des callbacks.
- `theme.py` importe les seuils de `services.stats` (unique dépendance « UI → service »),
  et `data/curriculum.py` importe `DEFAULT_DOMAIN_COLORS` de `theme` pour la graine.
- `app.py` est le seul à connaître `plan + progression + vues` simultanément.

## Deux fichiers d'état, deux responsabilités

| Fichier | Classe | Contenu | Sémantique |
|---|---|---|---|
| `neuro_plan.json` | `data/plan_store.PlanStore` | domaines, blocs, tâches | **structure** (modifiable) |
| `neuro_progress.json` | `data/store.ProgressStore` | identifiants cochés, sessions | **avancement** (jetable) |

Cette séparation permet de régénérer entièrement un planning (LLM, import) sans
perdre les statistiques, et de remettre la progression à zéro sans toucher au plan.
Les deux passent par `data/jsonfile.py` (écriture atomique, quarantaine).

La progression est filtrée au chargement par les identifiants connus du plan :
supprimer une tâche ne laisse donc jamais de coche orpheline réutilisable.

## Flux de données

### Cocher une tâche

```text
clic sur une ligne
  └─ TaskRow._commit()                  affiche immédiatement l'état
      └─ NeuroPlanner._on_task_toggle(task, done)
          ├─ ProgressStore.set_done(tid, done)   → écriture atomique du JSON
          ├─ DayView.sync(completed)             → réaligne toutes les cases
          └─ NeuroPlanner.refresh_aggregates()
               ├─ DomainChart.refresh(...)       → barres + couleurs
               ├─ Header.set_week(...)           → % semaine
               ├─ Sidebar.set_week(...)          → résumé + focus
               ├─ TimerPanel.set_stats(...)
               └─ DayView.set_progress(...)      → barre du jour
```

### Éditer le plan (domaine ou tâche)

```text
bouton « Domaines… » / « + » / « ✎ »
  └─ NeuroPlanner.manage_domains() / add_task() / edit_task()
      ├─ DomainDialog(self, plan).run()      dialogue modal (grab_set + wait_window)
      │    └─ plan.add_domain() / delete_domain() / rename_domain() / add_task()…
      │         └─ PlanStore.save()          écriture atomique de neuro_plan.json
      └─ si dialog.changed: NeuroPlanner.on_plan_changed()
           ├─ ProgressStore.prune(plan.task_ids())   → purge des coches orphelines
           ├─ DayView.show(day, completed, colors)   → reconstruction du jour
           └─ refresh_aggregates()                   → graphique, en-têtes, nav
```

## Format du plan (cible d'un générateur)

```json
{
  "version": 1,
  "updated_at": "2026-11-14T23:41:00",
  "domains": [{ "name": "Dev & Archi", "color": "#7C9CFF" }],
  "days": {
    "lun": [
      {
        "start": "07:30",
        "end": "08:45",
        "title": "Dev & Archi",
        "intent": "Encodage profond",
        "tasks": [
          { "id": "lun-0-0", "label": "Architecture hexagonale…", "domain": "Dev & Archi", "minutes": 45 }
        ]
      }
    ]
  }
}
```

Règles de validation appliquées au chargement (`PlanStore._load`) :

- seuls les jours `lun…sam` sont retenus, dans cet ordre ;
- un domaine sans nom, dupliqué ou de couleur invalide est écarté (ou recoloré) ;
- une tâche sans `id` unique, sans intitulé, sans domaine, ou avec une durée hors
  `1…240` est ignorée ;
- un `domain` inconnu rencontré dans une tâche est **enregistré** automatiquement
  (aucune donnée perdue) ;
- les blocs gardent leur position : `bid` vaut `<jour>-<index>`.

**Identifiants stables.** Les tâches issues de la graine utilisent la convention
positionnelle historique `<jour>-<bloc>-<tâche>` (compatibilité avec les fichier de
progression existants). Toute tâche créée ensuite reçoit un identifiant
`t<8 hex>` qui ne dépend plus de sa position : ajouter ou supprimer des tâches ne
décale jamais les coches existantes.

## Pipeline d'import (chapitres → planning)

```text
 texte collé  ─┐
               ├─► services/chapters.parse_chapters ─┐
 LLM            │                                   │  list[Chapter]
  ├─ Ollama local ─────────────────────────────────┐ │
  └─ Groq / Gemini / Mistral (OpenAI-compatible) ─┴─┘
     via services/providers.create_client(settings)
                                                    ▼
                              services/generation.build_week(domain, revision)
                                                    │  dict[jour] -> tuple[Block]
                                                    ▼
                              ui/import_dialog : aperçu (describe_week)
                                                    │  « Appliquer » + confirmation
                                                    ▼
                       PlanStore.replace_week(week, prune_unused_domains=…)
                                                    │
                    app.on_plan_changed() ─ ProgressStore.prune + vues reconstruites
```

Trois décisions structurent l'implémentation :

1. **Le LLM ne produit que des chapitres**, jamais le planning. Un petit modèle
   local est fiable sur une liste de titres, beaucoup moins sur une grille horaire
   valide ; l'algorithme garantit les 5 h/jour et la présence de tous les chapitres.
2. **Rien n'est appliqué sans relecture** : la sortie du modèle atterrit dans la
   zone de texte, puis l'aperçu montre les 30 tâches avant confirmation.
3. **Aucun appel réseau dans les tests** : les clients acceptent un `transport`
   injectable (`Callable[[url, payload, headers, timeout], dict]`), et les tests
   d'erreur HTTP monkeypatchent `urllib.request.urlopen`.

### Fournisseurs

`services/providers.py` contient un registre : ajouter un fournisseur = ajouter une
entrée dans `PROVIDERS` (clé, libellé, `kind`, URL de base, variable
d'environnement, modèles suggérés, URL d'inscription). Deux `kind` suffisent :

| `kind` | Client | Exemples |
|---|---|---|
| `ollama` | `OllamaClient` (`/api/generate`) | Ollama local |
| `openai` | `OpenAiCompatClient` (`/chat/completions`) | Groq, Gemini, Mistral, OpenRouter… |

Tout client exposant `complete(prompt) -> str` et `models() -> list[str]` convient
(`generate_outline` l'accepte en paramètre).

### Clé d'API : où elle vit, comment elle est protégée

1. **Résolution** — `resolve_settings()` : fichier local > variables
   d'environnement > défauts. La variable générique `NEUROPLANNER_LLM_KEY` évite
   d'écrire quoi que ce soit sur disque si tu préfères.
2. **Stockage** — `data/llm_config.py` écrit `llm_settings.json` à côté de la
   progression (jamais dans le dépôt, ligne prévue dans `.gitignore`), avec
   `chmod 0600` lorsque les permissions POSIX existent.
3. **Confidentialité** — le champ `api_key` est `repr=False` (il n'apparaît pas
   dans les logs), `masked_key` ne montre que les 4 derniers caractères, et
   `llm.redact()` remplace la clé (et tout motif `sk…`/`gsk…`/`AIza…`) dans les
   messages d'erreur : une API qui renverrait la clé dans son corps de réponse ne
   peut pas la propager jusqu'à l'écran.

### Erreurs traduites

| HTTP | Message |
|---|---|
| 401 / 403 | « Clé refusée par <fournisseur> : vérifie qu'elle est valide et active. » |
| 404 | « Modèle ou URL introuvable chez <fournisseur>. » |
| 429 | « Quota atteint : attends une minute, change de modèle, ou reviens au local. » |
| 5xx | « <fournisseur> est momentanément indisponible. » |
| hors ligne | « Impossible de joindre <fournisseur> » + conseil (`ollama serve` pour Ollama) |

### Modèles et mode raisonnement

`LlmSettings(think=True)` transmet `"think": true` à Ollama (modèles `thinking`).
Mesuré sur la machine de développement, 6 chapitres : `qwen2.5:3b` ≈ 17 s,
`gemma4` ≈ 142 s, `gemma4` + raisonnement ≈ 161 s. Le raisonnement améliore
l'enchaînement des chapitres ; il est donc proposé en option, jamais imposé, et
masqué pour les fournisseurs hébergés (non supporté). Timeout par défaut : 300 s.

## Détails d'implémentation notables

- **Clics et survols** : CustomTkinter dessine dans des canvas internes ; un
  `bind` sur la racine ne suffit pas. `ui/widgets.py` parcourt l'arbre
  (`bind_tree`, `make_interactive`) et diffère la sortie de survol pour éviter
  le clignotement entre enfants.
- **Case à cocher et crayon** : exclus des binds de la ligne (`skip=(...)`) pour
  ne pas basculer deux fois la tâche quand on clique dessus.
- **Minuteur** : `services/countdown.py` s'appuie sur `time.monotonic` et une
  horloge injectable ; `ui/timer_panel.py` ne fait que planifier `after(100)`.
  La fin est signalée une seule fois par `tick() -> True`.
- **DPI/échelle** : CustomTkinter applique un facteur lié au DPI Windows
  (`_get_window_scaling()`), différent de celui de Tk. `app._apply_window_geometry()`
  fixe donc la taille **physique** de la fenêtre via `tk.Tk.geometry` tout en
  gardant des dimensions logiques cohérentes. Les dialogues font de même dans
  `ModalDialog._center()`.
- **Panneaux défilants** : la colonne de droite est un `CTkScrollableFrame` et la
  liste des domaines aussi : sur un écran bas, rien n'est coupé.
- **Domaines vides** : `stats.domain_progress(..., order=plan.domain_names)`
  renvoie **tous** les domaines de l'ordre fourni, même sans tâche ; le graphique
  les affiche en gris avec la mention « vide » plutôt qu'en rouge (0 % serait
  trompeur).
- **Un seul domaine minimum** : `delete_domain` refuse de supprimer le dernier,
  car une tâche doit toujours référencer un pilier existant.

## Tests

| Fichier | Portée | Écran requis |
|---|---|---|
| `test_curriculum.py` | graine : 6 jours, 4 blocs, 5 h, piliers, identifiants | non |
| `test_plan_store.py` | domaines, tâches, validation, persistance, `replace_week` | non |
| `test_chapters.py` | table des matières : puces, numéros, durées, doublons | non |
| `test_generation.py` | 5 h/jour, contenu complet, reliquats, déterminisme | non |
| `test_llm.py` | prompt, extraction JSON, erreurs réseau (transport factice) | non |
| `test_providers.py` | registre, réglages, client OpenAI-compatible, redaction, repli de modèle | non |
| `test_diagnostics.py` | rapport `--check-llm`, modèle obsolète, codes de sortie | non |
| `test_llm_config.py` | fichier de réglages, clé masquée, permissions | non |
| `test_stats.py` | agrégations, bornes, domaines vides | non |
| `test_countdown.py` | pause/reprise/fin, horloge simulée | non |
| `test_store.py` | écriture atomique, quarantaine, `prune`/`forget` | non |
| `test_core.py` | formats, chemins, palette | non |
| `test_ui_smoke.py` | fenêtre réelle : coche, navigation, reset, minuteur, reprise | **oui** |
| `test_ui_editing.py` | dialogues domaines/tâches et propagation aux vues | **oui** |
| `test_ui_import.py` | import : aperçu, application, assistant LLM (stub), prune | **oui** |

```powershell
python -m pytest                  # tout (327 tests, 1 ignoré sous Windows)
python -m pytest -m "not gui"     # sans écran (utilisé par la CI)
```

**Pièges des tests modaux** : ne jamais déclencher un bouton qui ouvre un vrai
`run()` (il appellerait `wait_window()` et bloquerait la suite). Soit on instancie
le dialogue et on appelle ses méthodes directement, soit on remplace
`neuroplanner.app.TaskDialog` / `DomainDialog` / `ImportDialog` par un stub (voir
`test_ui_editing.py`, `test_ui_import.py`). Toute action destructrice
(`replace_week`, `reset_week`) appelle `messagebox.askyesno` : il faut la
monkeypatcher, sinon la boîte native bloque le test.
