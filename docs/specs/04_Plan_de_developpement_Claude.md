# 04 — Plan de développement pour Claude Code

## Instructions de lancement à donner à Claude
> Tu développes **Sprite Builder Studio**, application Windows 11 locale en **Python + PySide6**, sans IA intégrée. Lis entièrement le dossier. Respecte les exigences confirmées et distingue-les des recommandations non confirmées. Travaille **par jalons**, sans supprimer une fonctionnalité existante ni réécrire destructivement le projet. Avant chaque gros changement, commit Git/backup ; après chaque jalon, exécute les tests et montre le résultat. Conçois le canevas, les données et la sauvegarde pour évoluer vers l’éditeur Pixel Art, les animations, étages, références partagées et export Godot. Ne bloque pas la première version sur les fonctions avancées. N’écrase jamais des assets utilisateur ou fichiers du jeu.

## Préparation (J0) — socle
- Initialiser dépôt Git et environnement Python isolé ; `pyproject.toml`, lint, tests unitaires, CI locale si possible.
- Construire la fenêtre PySide6 avec docks enregistrables, préférences et dossier de données utilisateur.
- Définir les identifiants UUID, schémas versionnés et interface entre rendu/métier/persistance.
- Livrables : application ouvrable, structure saine, tests de lancement et sauvegarde de préférences.

## J1 — MVP du canvas et des assets (priorité absolue)
**Découpage en 4 petites étapes (chacune testée avant la suivante) :**
- **J1a** — Import du kit : lecture des fiches JSON, copie des PNG, miniatures, catégories. *Test : 163 modules affichés.*
- **J1b** — Canvas : damier, zoom/pan, ajout d'un sprite par clic ou glisser-déposer, sélection, déplacement, suppression.
- **J1c** — Sauvegarde/chargement projet atomique + Z manuel. *Test : fermer, rouvrir, rien ne bouge.*
- **J1d** — Copier-coller et export PNG RGBA natif. *Test : pixels identiques.*

Contenu global de J1 :
- Bibliothèque simple : import du kit et de PNG isolés par copie, miniatures persistantes.
- Canvas : damier, zoom/pan, ajout par clic ou glisser-déposer, sélection, déplacement, suppression, copier-coller.
- Z manuel, export PNG RGBA natif, sauvegarde/chargement projet atomique.
- **Validation :** construire une petite maison de 10 modules **du kit**, fermer, rouvrir sans perte, exporter pixel-perfect ; recharger la recette `boulangerie` et obtenir le même assemblage que `assemblages/boulangerie_sprite.png`.

## J2 — Édition non destructive
- Historique undo/redo via commandes ; groupes ; multi-sélection ; guides et aimantation grille/bords.
- Étages + calques, visibilité/verrouillage, réorganisation et gestion explicite du Z.
- **Validation :** annuler 20 manipulations variées, rouvrir un projet avec plusieurs étages et masquer le toit.

## J3 — Modules et bibliothèque
- Ancrages nommés, aimantation entre modules, pivot éditable, dimensions libres.
- Ressources référencées, variantes, édition **instance vs source**, détection de références manquantes, favori/catégories/tags.
- **Validation :** placer 15 fenêtres, détacher une instance et modifier la source sans modifier cette instance.

## J4 — Atelier Pixel Art V1
- Outils pixel/gomme/pipette/remplissage/sélection, palette, calques, zoom net.
- Ouverture d’un module depuis la construction, retour avec confirmation de portée de modification.
- **Validation :** créer un sprite neuf et corriger un toit sans modifier une autre occurrence par erreur.

## J5 — Animation & répétition
- Timeline image par image, preview, import/export spritesheet.
- Répétition en ligne, grille et tracé, prévisualisation avant confirmation.
- **Validation :** produire une animation de porte et une clôture suivant une courbe simple.

## J6 — Prévisualisations & interopérabilité
- Environnement de référence et fonds, éclairage/ombres non destructifs (simulation clairement identifiée) à partir des cartes de normales (`_n`) et d'émission (`_e`) du kit ; comparer avec `apercus/kit_village_scene_lumiere.png`.
- Export JSON structuré et export vers scène Godot 4 via plugin d’export isolé.
- **Validation :** importer une scène exportée dans un projet Godot de test ; comparer positions, ordre des calques et transparence.

## J7 — Stabilisation / ergonomie
- Sauvegardes versionnées et récupération après crash ; import de lots et gestion des formats additionnels choisis.
- Options UI, espaces de travail, raccourcis, optimisations mémoire/profilage.
- Paquet Windows exécutable ; guide utilisateur ; tests d’installation.
- **Validation :** démonstration complète et passage de toutes les vérifications `05_Plan_de_tests.md`.

## Priorités et périmètre
| Niveau | Fonction |
|---|---|
| P0 | Import PNG, canvas manuel, manipulation, sauvegarde, export PNG |
| P1 | Étages/calques, ancrages, groupes, références et undo/redo |
| P2 | Pixel Art complet, variantes, animation, répétitions |
| P3 | Aperçu dynamique, export Godot avancé, optimisations massives, extensions |

**Attention :** J0–J7 sont des **jalons**, pas des engagements en nombre de jours. Claude doit annoncer ce qui est réellement terminé et testé à chaque jalon, et ne jamais marquer un module « fait » si seule son interface existe.

## Protocole de livraison par jalon
1. Fichiers modifiés + raison de chaque changement.
2. Démo ou captures de l’UI pour les fonctions visibles.
3. Commandes de test et résultats observés.
4. Sauvegarde/commit de restauration.
5. Liste des limites restantes, sans masquer les bugs.

## Dépendances bloquantes à éviter
- Ne pas coder le pixel editor directement dans le même objet que le canvas de construction.
- Ne pas figer le projet en bitmap aplati : conserver les instances de modules.
- Ne pas lier l’export PNG au seul moteur Qt sans comparaison de pixel exact.
- Ne pas imposer un export Godot avant une sauvegarde native fiable.
- Ne pas intégrer d’IA (exclue du périmètre retenu).
