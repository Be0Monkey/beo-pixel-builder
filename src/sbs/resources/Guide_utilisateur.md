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
- **Mur en perspective (s'éloigne en diagonale)** : dans **Répéter…**, choisis « Mur en perspective ». Le point de départ
  est le **coin bas-gauche** de la première pièce (la plus proche, taille normale). Règle le **nombre** de pièces,
  la **pente du sol** (−50 % = le mur monte d'1 pixel pour 2 pixels vers la droite) et la **hauteur au loin**
  (ex. 50 %). Chaque pièce est déformée pour que ses bords touchent exactement ceux de sa voisine : le haut et le
  bas du mur forment deux lignes droites qui se rejoignent, sans escalier ni trou. Un nouveau module est créé par
  pièce (40 maximum). Pixels « au plus proche » (pas de flou), la pièce la plus proche passe devant.
  L'aperçu montre seulement les positions ; les variantes ne sont pas reprises.
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

## 12. L'édition web et le téléphone

Tu peux assembler une scène sur ton téléphone avec l'édition web de Sprite Builder Studio (onglet « Assembler »), puis la récupérer sur le PC.

1. **PC → téléphone** : menu Fichier, « Exporter la bibliothèque pour le téléphone ». Envoie le fichier obtenu sur le téléphone (câble, e-mail, messagerie) et, dans l'Atelier Pixel, onglet Assembler → Scène → « Importer la bibliothèque du PC ». Compte quelques secondes pour un gros kit (plusieurs centaines de modules).
2. **Sur le téléphone** : choisis un module, touche la scène pour le poser ; outil Sélection pour déplacer, flèches pour ajuster, devant/derrière, dupliquer, supprimer. Les dessins faits dans l'Atelier Pixel s'ajoutent aux modules avec « → Mes modules » (point d'appui en bas au centre, réglable).
3. **Téléphone → PC** : onglet Scène → « Partager avec le PC » (ou « Enregistrer le fichier »). Sur le PC : menu Fichier, « Importer une scène du téléphone ». Les modules absents sont ajoutés à la bibliothèque, les autres réutilisés ; la scène s'ouvre comme un projet non enregistré.

Confort de l'édition web :
- **Raccourcis clavier (PC)** : Ctrl+D dupliquer, Ctrl+C / Ctrl+V copier-coller (même entre scènes), Ctrl+A tout sélectionner, Ctrl+G grouper (+Maj : dégrouper), Suppr effacer, flèches 1 pixel, Maj+flèches une case de grille.
- **Aperçu avant de valider** : dans Objet → Répéter, les copies (ou le mur en perspective) s'affichent en transparence sur la scène avant de toucher « Créer ». Les derniers réglages sont retenus.
- **Favoris et récents** : l'étoile d'un module le met dans « ★ Favoris » ; la rangée « Récents » rappelle les derniers modules posés.
- **Sauvegarde complète** : onglet Scène → « Sauvegarde complète » crée un seul fichier (modules, scènes, animations, favoris) ; « Restaurer une sauvegarde » le remet sans rien supprimer.
- **Versions** : onglet Scène → « Versions de cette scène ». Une photo de la scène est prise toutes les 10 minutes de travail (20 gardées) ou à la demande ; « Restaurer » revient en arrière en gardant l'état actuel comme version.
- **Masquer un module** : le bouton ⊘ d'une vignette (ou « Masquer » dans la barre du module choisi) le retire de la liste sans le supprimer ; il reste dans tes scènes. L'onglet « Masqués » permet de le démasquer (↺).
- **Modifier un module avec Dessiner** : « Modifier avec Dessiner » (barre du module choisi, ou onglet Objet) ouvre l'image dans Dessiner (128×128 maximum). Puis « Mettre à jour le module » remplace l'image partout où elle est posée ; « → Mes modules » en crée au contraire une copie. Le point d'appui est conservé.
- **Palette de Dessiner** : trois palettes au choix (elfvsorc, couleurs du kit tirées des modules, base du PC), une rangée « Récentes », la saisie d'un code (#rrggbb) et « Retirer des couleurs » pour nettoyer « Mes couleurs ».
- **Remplacer une couleur** : dans Dessiner, onglet Couleurs → « Remplacer une couleur » : touche la couleur à changer sur le dessin, puis « Remplacer par la couleur actuelle » (sur le calque actif, ou tous les calques). Sur le PC : outil « Remplacer couleur » (R), choisis d'abord la nouvelle couleur, puis clique un pixel de l'ancienne.
- **Nuances** : sous la palette, 7 nuances de la couleur choisie (ombres vers le bleu, lumières vers le jaune).
- **Tablette graphique** : boutons « Lissage » (adoucit les tremblements) et « Pixel parfait » (supprime les coins en double) ; le bout gomme du stylet efface. Pixel parfait agit sur le pinceau de 1 pixel, sans miroir.
- **Recadrer au contenu** (onglet Calques) réduit la toile à la zone dessinée ; « Annuler le recadrage » le défait.
- **Poser dans la scène** (Ctrl+Entrée dans Dessiner) : ajoute le sprite aux modules (ou met à jour celui qu'on modifie) et passe à la scène avec ce module prêt à poser.
- **Miroir horizontal** et **Aligner** (gauche, centre, droite, haut, milieu, bas, répartir) dans l'onglet Objet. Le miroir crée un module « … (miroir) » réutilisé ensuite.
- **Aide** : la touche ? (ou le bouton ?) affiche tous les raccourcis. « Enregistré à HH:MM » indique la dernière sauvegarde de la scène.
- **Téléphone** : le bouton « Panneau » replie le panneau pour voir toute la scène ; les boutons sont plus grands au doigt.

Limites : le paquet scène ne transporte que les modules, les positions, les étages, les groupes et les animations (pas de variantes ni de cartes de normales) ; vider les données du navigateur efface modules et scènes, d'où l'intérêt de la sauvegarde complète.

## Sur PC : retourner et aligner

Menu **Édition** : **Retourner (miroir horizontal)** (Ctrl+M) crée un module « … (miroir) » (le point d'appui et les ancrages sont retournés aussi ; les variantes ne sont pas reprises) et l'applique aux objets sélectionnés. **Aligner** range les objets ou groupes sélectionnés : à gauche, au centre, à droite, en haut, au milieu, en bas, ou répartis à égale distance (au moins trois). Tout s'annule d'un seul Ctrl+Z.
