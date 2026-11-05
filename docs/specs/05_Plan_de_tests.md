# 05 — Plan de tests et d’acceptation

## A. Données de démonstration
**Jeu d'essai principal : le kit Blender fourni** (163 modules, 768 PNG, 17 recettes, voir `07`). Il couvre déjà des tailles variées (16×44, 34×19, arbres, bâtiments...), des variantes, des normales et des émissions.
À créer en plus (non couverts par le kit) : un sprite animé de 4 frames, une image corrompue, deux PNG de même nom et de contenus différents, un PNG semi-transparent.

## B. Tests unitaires prioritaires
| ID | Test | Résultat attendu |
|---|---|---|
| T01 | Sauvegarder puis charger une scène | Identifiants, positions et ordre identiques |
| T02 | Importer deux PNG de même nom, contenus différents | Aucune écrasement ; UUID distincts |
| T03 | Grouper/dégrouper et undo | Transformations réversibles |
| T04 | Déplacer une instance puis annuler | Position restaurée exactement |
| T05 | Détacher une instance d’une source partagée | Seule l’instance se modifie ensuite |
| T06 | Modifier la source partagée | Seules les instances liées sont mises à jour |
| T07 | Pivots et ancres | Alignement des points de connexion au pixel demandé |
| T08 | Trier à profondeur égale | Ordre stable et déterministe |
| T09 | Exporter PNG transparent | Canal alpha et couleurs RGBA préservés |
| T10 | Recharger une ancienne version de projet | Migration sûre ou erreur explicite |
| T11 | Chemin manquant / image corrompue | Message compréhensible ; projet non détruit |
| T12 | Écriture interrompue en autosave | Dernière sauvegarde saine récupérable |
| T13 | Importer le kit complet | 163 modules, 15 catégories, ancrages = `ancrage_px` des fiches |
| T14 | Importer les variantes d'un module (ex. `angle_rdc_droit__gres`) | Rattachées au même asset, pas de doublon |
| T15 | Charger la recette `boulangerie` | 16 éléments, positions identiques au JSON ; rendu = `assemblages/boulangerie_sprite.png` : 0 pixel de différence (convention : pivot en (x, −y), voir `07` §5) |
| T16 | Fiche JSON incomplète (ex. sans `depth` ni `pente`) | Valeurs par défaut sûres, pas de plantage |
| T17 | Groupes imbriqués : 3 niveaux OK, 4e refusé, cycle refusé | Message clair |

## C. Scénarios utilisateur de bout en bout
**S01 — Maison simple :** importer 10 éléments, assembler au pixel près, grouper, enregistrer, rouvrir, exporter un PNG. Comparer visuellement et par positions.

**S02 — Maison avec étage :** RDC + étage 1 + toit ; masquer le toit, verrouiller RDC, déplacer l’étage ; vérifier que le RDC ne bouge pas.

**S03 — Fenêtre partagée :** placer 15 occurrences d’un même module ; retoucher une seule instance ; modifier ensuite la source ; vérifier 14 occurrences mises à jour et 1 indépendante.

**S04 — Perspective 3/4 :** placer arbre, clôture et personnage-test ; contrôler auto-profondeur, corriger manuellement et vérifier l’ordre après sauvegarde.

**S05 — Pixel Art :** créer une tuile de zéro, ajouter palette et transparence, utiliser un masque, sauvegarder ; les pixels doivent rester nets au zoom 800 %.

**S06 — Animation :** composer 4 frames, régler FPS, visualiser, exporter spritesheet ; recharger sans désynchronisation.

**S07 — Répétition :** répéter une clôture en ligne, grille et le long d’un tracé ; confirmer que chaque élément reste éditable.

**S08 — Godot (phase avancée) :** ouvrir l’export dans Godot 4 ; vérifier chemins relatifs, positions, transparence, pivots et ordre d’affichage.

## D. Tests d’ergonomie
- Un nouvel utilisateur importe et place son premier sprite sans tutoriel obligatoire.
- Pan/zoom/sélection contrôlables uniquement à la souris ; clavier en accélérateur, pas en obligation.
- Grilles et ancrages montrent clairement leur état et peuvent être désactivés immédiatement.
- Aucun panneau indispensable ne devient définitivement inaccessible après personnalisation.
- Fermeture avec modifications non enregistrées : demande de sauvegarde ou récupération disponible.

## E. Compatibilité
- Windows 11 ; écran 1920×1080 et 2560×1440 ; échelles 100 %, 125 %, 150 %.
- Noms français accentués, chemins contenant espaces, import depuis dossier en lecture seule, dossiers très longs.
- Fichiers PNG RGBA, images non carrées, transparences complexes et dimensions hors standards.

## F. Charge et performance
- 1 000 objets sans gel perceptible sur gestes simples ; mesurer latence réelle.
- 5 000 puis 20 000 objets : profiler et documenter les seuils plutôt que promettre une fluidité non mesurée.
- Import de 1 000 fichiers : interface réactive, progression et annulation.
- Longue session : pas de fuite mémoire croissante évidente ; sauvegarde d’un gros projet fiable.

## G. Résilience / sécurité
- Copier les ressources à l’import, ne jamais écraser les originaux ; ne jamais modifier fichiers Godot existants implicitement.
- Échec d’export (dossier non accessible / disque plein) : message explicite, fichier précédent inchangé.
- Projet volontairement malformé : ne pas exécuter de code, afficher erreur propre.
- Simuler crash pendant autosave et vérifier récupération correcte.

## H. Définition de « terminé »
Une fonctionnalité est « terminée » uniquement si : comportement fonctionnel, résultat visible, tests passés, persistance assurée si nécessaire, possibilité d’annuler, absence de régression connue majeure, et limite documentée. La simple présence d’un bouton ne suffit pas.
