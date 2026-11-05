# Sprite Builder Studio — guide utilisateur

Sprite Builder Studio est un atelier **local** (rien n'est envoyé sur Internet, aucune IA) pour
**assembler à la main** des sprites 2D en vue 3/4, comme avec des briques LEGO : tu poses des modules
(murs, toits, arbres…), tu les ajustes au pixel près, puis tu exportes une image ou une scène Godot.

## 1. Premier lancement : importer tes sprites
1. Dans le panneau **Bibliothèque** (à gauche), clique **Importer le kit de sprites…** et choisis le
   dossier du kit. Ton dossier d'origine n'est **jamais modifié** : l'application en garde une copie.
2. Tu as d'autres images ? **Importer des images…** accepte des fichiers ou un dossier entier
   (sous-dossiers inclus). Formats : PNG (conservé tel quel), GIF, BMP, WebP (convertis en PNG ;
   pour un GIF animé, seule la première image est prise).
   - Une image déjà importée (même contenu) n'est pas dupliquée.
   - Deux images de même nom mais de contenu différent restent deux modules distincts.
   - Une image abîmée ou trop grande (plus de 4096 px) est signalée et ignorée, le reste continue.

## 2. Assembler
- **Glisser** un module de la bibliothèque vers l'espace de travail, ou **double-clic** pour le poser au centre.
- **Déplacer** à la souris (les pixels restent entiers) ou aux **flèches** du clavier.
- **Zoom** : molette ou `Ctrl +` / `Ctrl −` ; `Ctrl 0` revient à 200 %. Les pixels restent nets.
- **Aimants** (menu Vue ou barre d'outils) : grille, bords, ancrages. Maintiens **Alt** pendant un
  glissement pour couper l'aimant. Chacun peut être désactivé d'un clic.
- **Ordre de recouvrement** : automatique (par profondeur). `Ctrl ]` met devant, `Ctrl [` derrière,
  `Ctrl \` revient à l'automatique.
- **Annuler / Rétablir** : `Ctrl Z` / `Ctrl Y`. Toute action est annulable.

## 3. Organiser
- **Étages et calques** (panneau de droite) : masquer, verrouiller, réordonner, dupliquer un étage.
- **Groupes** : `Ctrl G` groupe, `Ctrl Shift G` dégroupe (3 niveaux maximum). Double-clic pour entrer dans un groupe.
- **Répéter…** (`Ctrl R`) : une clôture en ligne, en grille ou le long d'un tracé ; chaque élément reste modifiable.
- **Redimensionner…** (`F5`) : agrandit (×2 à ×8) ou réduit (÷2 à ÷4) un module **avec des pixels toujours nets**
  (facteurs entiers). Un **nouveau module** est créé ; l'original n'est pas modifié. Coche « Remplacer les objets
  sélectionnés » pour les mettre à jour d'un coup (même position, annulable avec `Ctrl Z`). Réduire exige une taille
  divisible par le facteur (sinon l'image serait déformée). Les variantes ne sont pas reprises.
- **Couvrir une longueur** : dans **Répéter…**, choisis « Couvrir une longueur » : indique la largeur (ou hauteur) à
  remplir et la taille d'une pièce (proposée d'après le module). « Tout couvrir » dépasse un peu à la fin,
  « Pièces entières » peut laisser un vide, « Exact » finit pile à la longueur avec un léger chevauchement.
- **Propriétés du module…** (`F4`) : pivot, ancrages, favoris, mots-clés. Tu peux modifier la source
  (toutes les occurrences changent) ou seulement une copie locale.

## 4. Dessiner et animer
- **Modifier les pixels…** (`F6`) et **Nouveau sprite…** : crayon, gomme, pipette, remplissage, sélection, calques, palette.
- **Animations…** (`F7`) : compose des images, règle la vitesse, visualise, exporte une planche (spritesheet).

## 5. Enregistrer, versions et récupération
- **Enregistrer** (`Ctrl S`) : fichier `.sbsproj`. L'écriture est « atomique » : une coupure ne peut pas abîmer le projet.
- **À chaque enregistrement**, une copie datée est rangée (10 versions par projet par défaut).
  **Fichier › Versions et récupération…** permet de rouvrir une ancienne version (elle s'ouvre comme
  une copie : ton projet actuel n'est pas touché).
- **Sauvegarde automatique** (toutes les 2 minutes par défaut, réglable) : si l'application s'arrête
  brutalement (coupure, plantage), au prochain démarrage elle propose de **récupérer** ton travail non enregistré.
  Utilise une seule fenêtre de l'application à la fois.
- Un projet ouvert sur un autre ordinateur se rattache à la bibliothèque locale par le kit d'origine.
  Les images introuvables apparaissent en **rose avec « ? »** : rien n'est supprimé.

## 6. Exporter
- **PNG** (`Ctrl E`) : transparence conservée, option d'agrandissement entier (pixels nets).
- **Godot 4** : une scène `.tscn` (étages, calques, ordre de dessin, pivots) + les textures. Un
  dossier déjà rempli par autre chose n'est jamais écrasé.
- **JSON** : toutes les positions, l'ordre, les groupes et les animations, pour d'autres outils.

## 7. Aperçu éclairé (`F8`) — une simulation
Montre ta scène avec une lumière réglable (direction, hauteur, ombres), d'après les cartes de relief
et d'émission du kit. C'est une **approximation** : elle n'est jamais écrite dans tes sprites et ne
remplace pas un rendu Blender.

## 8. Personnaliser
- **Fichier › Options…** (`Ctrl ,`) : fréquence de la sauvegarde automatique, nombre de versions, **raccourcis
  clavier** (onglet dédié, avec détection des doublons et retour aux valeurs par défaut).
- **Vue › Espaces de travail** : enregistre la disposition actuelle des panneaux sous un nom et rappelle-la.
  **Réinitialiser les panneaux** rétablit tout si un panneau a disparu.
- **Vue › Fond de l'espace de travail** : damier ou couleur unie (ciel, herbe, terre, nuit, gris).

## 9. Raccourcis principaux (modifiables)
| Action | Raccourci |
|---|---|
| Nouveau / Ouvrir / Enregistrer | Ctrl N / Ctrl O / Ctrl S |
| Annuler / Rétablir | Ctrl Z / Ctrl Y |
| Copier / Couper / Coller / Dupliquer | Ctrl C / X / V / D |
| Supprimer | Suppr |
| Grouper / Dégrouper | Ctrl G / Ctrl Shift G |
| Grille | G |
| Zoom + / − / 200 % | Ctrl + / Ctrl − / Ctrl 0 |
| Pixels / Animations / Propriétés / Aperçu / Redimensionner | F6 / F7 / F4 / F8 / F5 |
| Guide / Options | F1 / Ctrl , |

## 10. En cas de problème
- **Un message d'erreur** explique ce qui s'est passé ; le projet ouvert n'est jamais détruit.
- **Vérifier l'installation** : lance `SpriteBuilderStudio-console.exe --selftest` dans une console ; il affiche « tout fonctionne » ou la liste des échecs (ou `--selftest --report rapport.txt`).
- **Tes données** (préférences, bibliothèque, versions, copies de secours) sont dans
  `%APPDATA%\SpriteBuilderStudio`. Pour repartir de zéro, ferme l'application et renomme ce dossier.

## 11. Limites connues
- Installe l'application dans un dossier au **chemin court** (moins de 200 caractères) : Windows ne lance pas un programme dont le chemin dépasse 260 caractères.
- Une seule scène par projet.
- L'aperçu éclairé est une approximation ; l'export Godot ne crée pas d'AnimatedSprite (les animations sont dans le JSON et les planches).
- Très grosses scènes : voir `docs/Performances.md` pour les seuils mesurés.
