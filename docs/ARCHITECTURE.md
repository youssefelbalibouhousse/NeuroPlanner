# Architecture

Document destiné à celui qui **modifie** le projet. Il décrit les couches, le flux
de données et les recettes pour les changements les plus fréquents.

## Couches

```text
┌──────────────────────────────────────────────────────────────┐
│ ui/            widgets CustomTkinter (aucune décision métier)│
│  sidebar  header  day_view  block_card  task_row            │
│  timer_panel  chart  widgets (helpers d'interaction)        │
└───────────────▲───────────────────────────┬──────────────────┘
                │ callbacks                 │ lecture
┌───────────────┴───────────────────────────▼──────────────────┐
│ app.py         orchestration : état courant, jour affiché    │
└───────────────▲───────────────────────────┬──────────────────┘
                │                           │
┌───────────────┴──────────┐   ┌────────────▼─────────────────┐
│ services/                │   │ data/                        │
│  stats     (calculs purs)│   │  curriculum (plan figé)      │
│  countdown (temps pur)   │   │  presets    (minuteurs)      │
│  sound     (audio)       │   │  store      (JSON persistant)│
└───────────────▲──────────┘   └────────────┬─────────────────┘
                │                           │
            ┌───┴───────────────────────────▼──┐
            │ models.py (dataclasses immuables)│
            └──────────────────────────────────┘
```

Règles de dépendance :

- `models.py` ne dépend de rien (sauf `__future__`).
- `services/stats.py` ne connaît ni Tk ni CustomTkinter : il manipule
  `models.DayPlan` et un ensemble d'identifiants terminés.
- `ui/` ne décide jamais de l'état : il affiche et remonte des callbacks.
- `theme.py` importe les seuils de `services.stats` (unique dépendance « UI → service »).
- `app.py` est le seul à connaître `store + curriculum + vues` simultanément.

## Flux de données

```text
clic sur une tâche
  └─ TaskRow._commit()            affiche immédiatement l'état
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

Le JSON est la source de vérité : `store.completed` est relu par toutes les vues,
ce qui rend un `reset` ou un redémarrage trivialement cohérent.

## Identifiants de tâches

Chaque tâche reçoit `<jour>-<bloc>-<tâche>`, par exemple `mer-2-1`
(Mercredi, 3ᵉ bloc, 2ᵉ tâche). Ces identifiants sont la clé du fichier de
progression : **modifier l'ordre des tâches invalide les coches existantes**
(elles sont alors ignorées au chargement, sans erreur).

## Recettes

### Ajouter ou modifier une tâche

`neuroplanner/data/curriculum.py` → fonction `_day(...)` du jour concerné :

```python
"mer": _day(
    "Concurrence : async, backpressure, annulation",
    "Refactor d'un pipeline asynchrone",
    ...
),
```

Les 7 arguments sont : dev (cours), dev (lab), IA (cours), IA (lab),
projet SilenceLess, projet LocalArabi_RAG, arabe. Pour ajouter une tâche,
éditez la liste du bloc voulu dans `_day` :

```python
Block("09:00", "10:15", "IA & World Models", "Concepts & intuition",
      tasks=(
          Task(ia_core, "IA & World Models", 45),
          Task(ia_lab, "IA & World Models", 30),
      )),
```

Convention : garder **4 blocs** et **300 minutes** par jour ; les tests
`tests/test_curriculum.py` le vérifient.

### Ajouter un pilier

1. `curriculum.py` : utiliser le nouveau libellé comme `domain` d'une tâche.
2. `theme.py` : ajouter sa couleur dans `DOMAIN_COLORS` (et `DOMAIN_SHORT` pour
   le libellé du graphique).
3. `curriculum.DOMAINS` : ajouter le pilier dans l'ordre d'affichage souhaité.

### Ajouter un minuteur

`neuroplanner/data/presets.py` :

```python
TimerPreset(
    key="recall",
    label="Rappel 20",
    seconds=20 * 60,
    caption="Rappel 20 min · restitution d'un chapitre entier.",
    finished_hint="Rappel terminé — compare avec la source.",
),
```

L'interface et le `SegmentedButton` se mettent à jour automatiquement.

### Changer les couleurs

`theme.py` : éditer `DARK` (instance de `Palette`). Toutes les vues lisent
`PALETTE.*` ; aucune couleur n'est codée en dur dans `ui/`. Les seuils
(50 % / 80 %) sont dans `services/stats.py`.

### Ajouter une vue ou un panneau

1. Créer `neuroplanner/ui/mon_panneau.py` avec un `ctk.CTkFrame` exposant des
   méthodes `set_*` (pas d'accès au store).
2. L'instancier dans `NeuroPlanner._build_layout()` et l'appeler depuis
   `refresh_aggregates()`.
3. Ajouter un test `gui` dans `tests/test_ui_smoke.py`.

## Détails d'implémentation notables

- **Clics et survols** : CustomTkinter dessine dans des canvas internes ; un
  `bind` sur la racine ne suffit pas. `ui/widgets.py` parcourt l'arbre
  (`bind_tree`, `make_interactive`) et diffère la sortie de survol pour éviter
  le clignotement entre enfants.
- **Case à cocher** : elle est exclue des binds de la ligne (`skip=self.check`)
  pour ne pas basculer deux fois.
- **Minuteur** : `services/countdown.py` s'appuie sur `time.monotonic` et une
  horloge injectable ; `ui/timer_panel.py` ne fait que planifier `after(100)`.
  La fin est signalée une seule fois par `tick() -> True`.
- **DPI/échelle** : CustomTkinter applique un facteur lié au DPI Windows
  (`_get_window_scaling()`), différent de celui de Tk. `app._apply_window_geometry()`
  fixe donc la taille **physique** de la fenêtre via `tk.Tk.geometry` tout en
  gardant des dimensions logiques cohérentes, pour qu'elle tienne toujours à
  l'écran (testé sur 1280×720 à 150 %).
- **Panneaux défilants** : la colonne de droite est un `CTkScrollableFrame` :
  sur un écran bas, minuteurs et graphique restent accessibles au lieu d'être
  coupés.

## Tests

| Fichier | Portée | Écran requis |
|---|---|---|
| `test_curriculum.py` | 6 jours, 4 blocs, 5 h, 5 piliers, identifiants | non |
| `test_stats.py` | agrégations, bornes, seuils | non |
| `test_countdown.py` | pause/reprise/fin, horloge simulée | non |
| `test_store.py` | écriture atomique, quarantaine, migration | non |
| `test_core.py` | formats, chemins, palette | non |
| `test_ui_smoke.py` | vraie fenêtre : coche, navigation, reset, minuteur, reprise | **oui** |

```powershell
python -m pytest                  # tout
python -m pytest -m "not gui"     # sans écran (utilisé par la CI)
```
