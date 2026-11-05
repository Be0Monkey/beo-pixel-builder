# 01 — Cahier des charges fonctionnel

## 1. Vision
Offrir un **atelier de construction 2D modulaire** dans lequel l’utilisateur assemble des éléments graphiques existants comme des briques de LEGO : murs, portes, fenêtres, toitures, sols, arbres, rochers, clôtures et décorations. L’outil doit rester **simple et ergonomique**, même en présence d’options puissantes. Le rendu est du pixel art 2D, principalement en perspective 3/4 ; aucune conversion 3D implicite n’est requise.

## 2. Contraintes confirmées
- Plateforme principale : **Windows 11** ; usage local.
- Technologie prévue : **Python + PySide6**.
- **Pas d’assistant IA intégré** dans la configuration retenue.
- Assemblage **manuel** (pas de génération automatique de bâtiments).
- Bâtiments **et** décors ; perspective **3/4**.
- Deux ateliers métier : **Construction** et **Pixel Art / Animation**, plus la **Bibliothèque**.
- La priorité UX est la prise en main immédiate : glisser-déposer, manipulation directe et commandes visibles.

## 3. Atelier Construction
### 3.1 Canvas
- Afficher un canevas de taille extensible avec fond transparent (damier), zoom centré sur le pointeur, déplacement panoramique, repères et grille affichables.
- Sélection simple / multiple, rectangle de sélection ; déplacement précis au clavier ; glisser-déposer depuis la bibliothèque.
- Translation, retournement (miroir), échelle **par facteurs entiers** (×2, ×3) ; **pas de rotation libre** (elle déforme le pixel art ; le kit fournit déjà les versions gauche/droite). Rotation par pas de 90° réservée à une évolution ultérieure. **Conserver les pixels nets** : filtrage « voisin le plus proche » uniquement.
- Copier/coller, dupliquer, grouper/dégrouper ; objets composites éditables à l’intérieur du groupe.
- Guides d’alignement dynamiques, alignement/distribution, Ctrl + glisser pour dupliquer, actions contextuelles adaptées à la sélection.
- Annuler/rétablir chaque opération par commande réversible, y compris sur plusieurs éléments.

### 3.2 Placement et aimantation
Trois types **activables indépendamment** : (1) grille ; (2) bords/boîtes englobantes ; (3) **points d’ancrage configurables**. Priorité et seuil de capture paramétrables ; touche de désactivation temporaire pendant un glisser-déposer. L’aimantation ne doit jamais empêcher l’ajustement au pixel près.

### 3.3 Perspective et ordre d’affichage
- Mode **ordre automatique** d’après une règle de profondeur liée à la position au sol (pivot / point de contact), mais possibilité de **forcer manuellement** devant/derrière pour chaque élément.
- Séparer clairement **coordonnées X/Y**, **pivot**, **étage**, **calque**, **ordre Z** et **profondeur calculée** ; ne jamais prétendre déduire parfaitement le volume d’un sprite 2D.
- Grille facultative : carrée, 3/4 personnalisée et placement libre. La grille 3/4 est une aide visuelle, pas un moteur 3D.
- **Valeurs de référence (issues du kit Blender, voir `07`)** : 16 px par mètre, case de grille de 32 px (2 m), élévation de caméra 30° (1 m de hauteur = 13,86 px, soit 16 × cos 30°). Ces valeurs sont lues dans les fiches de chaque module et restent réglables par projet.
- **Règle d'ordre d'affichage (décision D-C)** : étage, puis calque, puis profondeur automatique (Y du pivot au sol), puis Z manuel, puis ID en dernier recours. Un seul ordre, documenté, déterministe.

### 3.4 Étages, calques et groupes
- Chaque bâtiment peut comporter des étages logiques (fondations, RDC, étages supplémentaires, toit) **et** des calques indépendants au sein des étages.
- Afficher, masquer, verrouiller, renommer, réordonner, dupliquer étages et calques. Possibilité de déplacer un étage entier sans abîmer les autres.
- Grouper des éléments dans un ensemble réutilisable ; garder la possibilité de « rentrer dans » un groupe pour modifier ses sous-éléments.
- **Groupes imbriqués autorisés, 3 niveaux maximum** (décision D-B) ; les cycles restent interdits.
- **Groupe enregistré comme module = module composite** (décision D-E) : il garde la liste de ses éléments positionnés, comme une *recette* du kit (`recipes/*.json`), et non une image aplatie. Un export aplati reste possible à part.

### 3.5 Répétition et variantes
- Répétition en **ligne**, **grille**, et **le long d’un tracé**. Prévisualisation avant validation, comptage, espacement, orientation facultative ; résultat éditable individuellement.
- Un module peut proposer plusieurs variantes (mur neuf, abîmé, couvert de mousse, etc.). Remplacer la variante en préservant position et points d’ancrage lorsque compatibles.
- Création de variantes directement dans l’atelier Pixel Art : recoloration/palette, usure et petits détails manuels.

### 3.6 Modification « instance ou toutes les utilisations »
- Les objets placés sont des **instances** référencées à une ressource commune.
- Lorsque l’utilisateur édite une ressource utilisée ailleurs, proposer explicitement : **modifier uniquement cette instance** (copie indépendante) ou **mettre à jour la source** (toutes les instances liées).
- Prévisualiser l’impact et autoriser l’annulation ; préserver les variantes et transformations locales de chaque instance.

## 4. Atelier Pixel Art / Animation
Un véritable éditeur intégré, et non un simple outil de recadrage :
- Dessin pixel par pixel, gomme, pipette, remplissage, formes, sélection rectangle/lasso, transformation, zoom fort, palette personnalisée, transparence.
- Calques, visibilité, verrouillage, fusion, masques ; historique d’annulation et aperçu sur fond transparent.
- Création **de zéro** et édition de sprites existants, ainsi que des modules destinés à se connecter entre eux.
- Timeline d’animation **image par image** ; gestion des spritesheets et exportation des séquences.
- Gestion de points d’ancrage et de métadonnées des modules depuis l’éditeur.
- Quand un sprite est modifié : avertir avant mise à jour globale ; ne pas modifier silencieusement les fichiers sources externes.

## 5. Bibliothèque permanente
- Importer images/spritesheets/dossiers ; miniatures, catégories/sous-catégories libres, mots-clés, favoris, recherche.
- Conserver une bibliothèque persistante entre sessions ; possibilité d’ajouter des modules à tout moment.
- Empêcher l’écrasement accidentel des originaux : préférer **copie gérée** à l’import et identifiant unique par ressource.
- Enregistrer un groupe ou une partie de construction comme **nouveau module réutilisable**.
- Supporter plusieurs dimensions sans contrainte de taille, avec formats standards facultatifs.
- Mettre en évidence le sprite sélectionné et montrer ses dimensions, son pivot et ses points d’ancrage.

## 5 bis. Kit de sprites fourni
Un kit de **163 modules** (768 PNG) généré depuis Blender est fourni et sert de bibliothèque de départ et de jeu d'essai. L'application doit l'importer **directement à partir de ses fiches JSON** (ancrage, échelle, variantes, normales, émission) et lire ses **recettes** d'assemblage. Voir `07_Kit_de_sprites.md`.

## 6. Prévisualisation
- Aperçu isolé sur damier/fond coloré, mais aussi sur un **environnement de référence** (sol, décor/image importée).
- Prise en charge souhaitée de simulations d’**éclairage/ombres** et d’un aperçu comparable au rendu Godot. Le kit fournit pour chaque sprite une **carte de normales** (`_n`) et une **carte d'émission** (`_e`) : l'éclairage dynamique est donc réalisable (P3), pas seulement décoratif. Distinguer nettement **prévisualisation illustrative** et **rendu Godot réel**.
- Les effets de prévisualisation ne modifient jamais les pixels d’origine tant qu’ils ne sont pas explicitement appliqués.

## 7. Interface
- Panneaux déplaçables, redimensionnables, masquables ; espaces de travail personnalisés/enregistrés pour Construction, Pixel Art, Animation, Bibliothèque.
- Bibliothèque avec miniatures à gauche, canvas central, propriétés + arborescence étages/calques à droite, outils accessibles sans ouvrir dix menus.
- Raccourcis modifiables, menus contextuels, infobulles et état visible de l’aimantation / profondeur / calque actif.

## 8. Projets, sauvegardes et export — propositions à confirmer
Les éléments précis des réponses Q17–Q19 **ne sont pas retrouvés**. Définir la base technique de façon extensible :
- Format projet natif avec plusieurs constructions par projet, chaque construction exportable et ouvrable séparément.
- Sauvegarde manuelle, **autosave atomique**, versions de secours et récupération après crash.
- Exports : PNG transparent sans interpolation, PNG par calque, métadonnées JSON, spritesheet d’animation ; évolution possible vers scène **Godot 4** (`.tscn`) en veillant aux chemins relatifs et à la résolution du projet.
- Ne jamais écraser une scène existante du jeu sans confirmation.

## 9. Limites et hors périmètre initial
- **Aucune IA intégrée** ; pas de génération d’images par prompts.
- Pas de moteur de construction automatique, de modélisation 3D ou de simulation physique.
- Pas de promesse de transformation perspective parfaite via rotation d’image 2D.
- Collaboration cloud, marketplace et synchronisation distante non nécessaires au fonctionnement.
- Priorité au fonctionnement fiable du MVP avant tout outil de dessin ou d’éclairage très avancé.

## 10. Critères globaux d’acceptation
L’utilisateur doit pouvoir importer des modules, construire une maison avec étages et calques, régler l’ordre de recouvrement, créer un groupe, retoucher un module, choisir entre modification locale et globale, sauvegarder, rouvrir et exporter un PNG transparent **sans déplacement ni flou**.
