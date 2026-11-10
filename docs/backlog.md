# Backlog

Format : *En tant que… je veux… afin de…*, suivi des critères d'acceptation.
Statuts : ✅ fait · 🔄 à valider · 📋 à faire

## Sprint 1 — Prochains départs ✅

### US-01 Rechercher un arrêt du réseau Unireso ✅
En tant qu'usager, je veux trouver un arrêt (bus, tram, train ou bateau) par son nom ou autour de moi, afin d'en voir les départs.
- [x] La recherche se lance dès 2 caractères, avec un délai de 300 ms entre les frappes
- [x] Seuls les arrêts de la zone Genève et alentours sont proposés (option « toute la Suisse »)
- [x] Le bouton 📍 liste les arrêts proches, triés par distance

### US-02 Voir les prochains départs en temps réel ✅
En tant qu'usager, je veux voir les prochains départs d'un arrêt avec le temps restant, afin de savoir quand partir.
- [x] Compte à rebours en minutes, heure affichée au-delà de 60 minutes
- [x] Retard affiché (+X min) et heure réelle quand l'info existe
- [x] Quai ou voie affiché quand il est connu
- [x] Rafraîchissement automatique toutes les 30 secondes et au retour sur l'app

### US-03 Choisir les lignes affichées ✅
En tant qu'usager, je veux activer ou désactiver les lignes d'un arrêt, afin de ne voir que celles qui me concernent.
- [x] Une pastille par ligne, qui s'active ou se désactive d'un tap
- [x] Boutons « Toutes » et « Aucune »
- [x] Choix gardé pour chaque arrêt

### US-04 Retrouver mes arrêts rapidement ✅
En tant qu'usager régulier, je veux que mes arrêts habituels soient proposés en premier, afin d'accéder à mes départs sans chercher.
- [x] « Vos arrêts » triés par nombre de consultations
- [x] Le dernier arrêt consulté se rouvre au lancement

## Sprint 2 — Directions 🔄

### US-05 Filtrer par direction ✅ (à valider sur données réelles)
En tant qu'usager, je veux ne garder qu'une direction d'une ligne, afin de ne voir que les départs dans mon sens.
- [x] Une direction correspond à la ligne + le prochain arrêt : les courses partielles d'un même sens sont regroupées
- [x] Pastille partielle (ex. « 12 · 1/2 ») quand une partie des directions est masquée
- [x] Si toutes les directions sont décochées, toute la ligne est masquée
- [x] Les préférences du Sprint 1 sont reprises
- [ ] Vérifié sur données réelles : présence de `passList`, bateaux CGN et Mouettes, libellés des trains

## Candidats pour les prochains sprints 📋

### US-06 Présélection automatique des lignes les plus consultées
En tant qu'usager, je veux que les lignes que j'utilise le plus soient présélectionnées et affichées en premier, sans réglage manuel.
- Compter les consultations par ligne et direction (ex. départ affiché ou tapé)
- Trier les pastilles par usage, avec un réglage par défaut proposé et non imposé

### US-07 Itinéraire le plus rapide
En tant qu'usager, je veux un itinéraire de A à B optimisé sur la durée.

### US-08 Itinéraire avec le moins de marche
En tant qu'usager, je veux un itinéraire de A à B qui minimise la marche, même s'il est plus long.

### US-09 Priorité de déplacement mémorisée
En tant qu'usager, je veux choisir une fois ma priorité (rapide ou moins de marche) et qu'elle s'applique par défaut.

### TECH-01 Validation sur données réelles
Lister les codes de catégorie réels (trains, Léman Express, bateaux) et ajuster `CATS` et `lineLabel`.

### TECH-02 Hébergement des prototypes (GitHub Pages)
Pouvoir tester sur téléphone par un simple lien, sans télécharger de fichier.

### TECH-03 Emballage APK
Choisir l'enveloppe (Capacitor, PWA en TWA ou natif) et produire un premier APK à partir du prototype.
