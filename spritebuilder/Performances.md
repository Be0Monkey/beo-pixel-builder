# Performances mesurées (J7)

Mesures faites avec `python tools/benchmark.py` sur le PC de développement (Windows 11, Python 3.13,
PySide6, interface « hors écran »). Les valeurs sont des **ordres de grandeur** : elles dépendent de la machine.
Scène synthétique : 24 modules de tailles variées, positions aléatoires, 1 étage / 1 calque.

| Mesure (ms) | 1 000 objets | 5 000 objets | 20 000 objets |
|---|---|---|---|
| Ajout de N objets au modèle | 2 | 9 | 39 |
| Calcul de l'ordre de dessin | 1 | 6 | 27 |
| Enregistrement du projet | 14 | 24 | 55 |
| Relecture du projet | 18 | 28 | 69 |
| Export PNG (échelle 1, ≈32 Mpx à 20 000) | 68 | 292 | 1 132 |
| Création de la scène graphique | 33 | 59 | 186 |
| Sélectionner tout | 0 | 1 | 7 |
| Déplacer tout (1 geste) | 11 | 49 | 222 |
| Annuler ce déplacement | 6 | 30 | 133 |
| Tout supprimer | 5 | 21 | 111 |
| Annuler la suppression | 24 | 66 | 245 |
| Taille du projet (Mo) | 0,34 | 1,67 | 6,67 |
| Mémoire ajoutée (Mo) | ≈ 30 | ≈ 25 | ≈ 57 |

## Lecture
- **1 000 objets** : tout est instantané (< 70 ms), largement sous le seuil de gel perceptible (≈ 100 ms).
- **5 000 objets** : tous les gestes courants restent sous 100 ms ; l'export PNG prend 0,3 s.
- **20 000 objets** : gestes de groupe (déplacer/supprimer tout) entre 0,1 et 0,25 s ; export 1,1 s. Utilisable,
  mais on sent les opérations qui touchent tous les objets. Le projet pèse ≈ 7 Mo.
- Les temps croissent **linéairement** avec le nombre d'objets (pas de dégradation quadratique).
- **Longue session** (`--soak`) : 300 cycles « déplacer / annuler / rétablir » sur 2 000 objets : la mémoire
  passe de 56,5 à 57,3 Mo puis reste plate → pas de fuite visible.
- Le **rendu d'une image de la vue** (≈ 3 ms) ne concerne que la zone visible ; il n'a pas été mesuré
  avec un vrai écran graphique (mesure hors écran).

## Ce qui a été corrigé grâce aux mesures
| Problème trouvé | Avant | Après |
|---|---|---|
| Relecture : une requête SQLite par objet | 4 000 ms (20 000 obj.) | 69 ms |
| Export PNG : image rouverte pour chaque objet | 9 450 ms (20 000 obj.) | 1 132 ms |
| Scène graphique : une requête SQLite par objet | 2 265 ms (5 000 obj.) | 59 ms |
| Suppression : calculs en O(n²) | 539 ms (5 000 obj.) | 21 ms |
| Annulation de suppression : doublons testés en O(n²) | 2 742 ms (5 000 obj.) | 66 ms |

## Mémoire des images
Les images affichées sont gardées dans un cache limité à 256 Mo (les moins récemment utilisées sont oubliées
puis rechargées à la demande).

## Limites / à surveiller
- Au-delà de 20 000 objets non mesuré ; l'export PNG refuse une image de plus de 64 millions de pixels (protection voulue).
- Import de 1 000 fichiers : réalisé en arrière-plan avec progression et annulation ; le temps dépend du disque.
- Mesures non faites sur un PC plus modeste ni à 125 %/150 % d'échelle d'écran.
