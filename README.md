# swissPublicTransport

Application Android de transport public : d'abord le réseau genevois (Unireso / TPG, Léman Express, Mouettes, CGN), ensuite Lausanne, puis toute la Suisse.

Avant le passage en APK, chaque sprint livre un **prototype autonome** : un seul fichier HTML qui s'ouvre dans un navigateur, sans serveur ni installation.

## Principe directeur (cahier des charges)

L'application s'adapte à son utilisateur :
- les lignes et arrêts les plus consultés sont présélectionnés et affichés en premier ;
- l'accès aux prochains départs se fait en un minimum de gestes ;
- les itinéraires suivent la priorité de l'utilisateur (le plus rapide, le moins de marche, …).

## Prototypes

| Sprint | Dossier | Contenu |
|---|---|---|
| 1 | [`prototypes/sprint-01-departs`](prototypes/sprint-01-departs/index.html) | Recherche d'arrêt (zone Unireso), prochains départs en temps réel, sélection des lignes, arrêts fréquents |
| 2 | [`prototypes/sprint-02-directions`](prototypes/sprint-02-directions/index.html) | Filtre par direction (ligne + prochain arrêt), compatible avec les préférences du Sprint 1 |

Pour les essayer : télécharger le fichier `index.html` et l'ouvrir dans Chrome (téléphone ou ordinateur).

## Données

[transport.opendata.ch](https://transport.opendata.ch) : API ouverte, sans clé, CORS activé, qui couvre les horaires officiels suisses avec le temps réel quand il est disponible.
- `/v1/locations` : recherche d'arrêts (par nom ou par coordonnées)
- `/v1/stationboard` : prochains départs d'un arrêt (`passList` sert à identifier la direction)

Les préférences (arrêts consultés, lignes et directions masquées) sont gardées dans le `localStorage` de l'appareil, sous le préfixe `tpp:`.

## Tests

Tests de bout en bout avec Playwright. L'API est simulée par des données factices, ce qui rend les tests reproductibles sans réseau.

```bash
pip install -r tests/requirements.txt
python -m playwright install chromium   # ou CHROME_PATH=/chemin/vers/chrome
python tests/test_sprint01.py
python tests/test_sprint02.py            # captures d'écran dans tests/out/
```

## Organisation

- Backlog et user stories : [GitHub Issues](https://github.com/TiagSant/swissPublicTransport/issues), un milestone par sprint (conventions dans [`docs/backlog.md`](docs/backlog.md))
- Une branche et une pull request par sprint, avec revue de code par le product owner
