# Données réelles — transport.opendata.ch (relevé du 10.11.2026)

Validation TECH-01 (#10) faite depuis un navigateur, sur 12 arrêts : Bel-Air, Cornavin, Molard, Eaux-Vives (tram et gare), Petit-Lancy Les Esserts, Genève-Aéroport, Nyon, Lancy-Pont-Rouge, Champel, Annemasse, débarcadères des Pâquis et du Jardin-Anglais.

## Catégories observées → mode dans l'app

| `category` | `number` (exemples) | Opérateur | Mode | Libellé affiché |
|---|---|---|---|---|
| `T` | 12, 14, 15, 17, 18 | TPG | tram | `12` |
| `B` | 1, 2, 3 … 92, 23, 28 | TPG | bus | `3` |
| `B` | L1, L2, C33, C43 | SNCF | bus (car de substitution / TER routier) | `L1` |
| `BAT` | M1, M2, M3 | MGsa (Mouettes) | bateau | `M2` |
| `R` | L1, L2, L3, L4 | SBB | train (Léman Express) | `L4` |
| `TER` | L2, L3, C33, C43 | SNCF | train | `L2` (fusionné avec `R L2`) |
| `R` | 55 | NStCM | train | `R 55` |
| `RE` | 33 | SBB | train | `RE 33` |
| `IR` / `IC` | 15, 57, 90, 95 / 1 | SBB | train | `IR 90`, `IC 1` |
| `IR` | 001943 (numéro de course) | SBB | train | `IR` (repli prévu) |

Tous ces codes étaient déjà dans le mapping `CATS`, sans correction nécessaire.

## Autres champs
- **`passList` présent partout**, bateaux compris (2 entrées). Le filtre par direction (US-05) fonctionne : il prend le 2e élément comme prochain arrêt.
- **`stop.platform`** : lettre de quai TPG (A–Z), numéro de voie CFF, `null` pour les bateaux et à Annemasse.
- **`stop.delay` et `prognosis.departure`** : renseignés pour les TPG, les Mouettes et la plupart des trains ; `null` sur quelques IR et RE.
- **Recherche** : un nom court renvoie aussi des arrêts hors zone (« Bel-Air » → « Bel-Air LEB » à Lausanne) ; ils sont bien filtrés par la zone.
- **Icône d'arrêt `null`** sur certains débarcadères et sur « Bains des Pâquis ». Correction : les noms en « (lac) » sont traités comme des bateaux.
- Les débarcadères CGN (ex. Jardin-Anglais) n'avaient aucun départ au moment du relevé (horaire d'hiver probable). À revérifier en saison.
