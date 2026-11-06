# 06 — Décisions et traçabilité

## Pourquoi ce tableau existe
La conversation disponible contient des choix explicites jusqu’à **Q16**. L’échange sur téléphone annonçait **51 décisions validées**, mais leurs réponses individuelles (Q17–Q51) ne sont pas toutes récupérables. Il serait trompeur d’attribuer « C » automatiquement aux questions restantes.

## Décisions confirmées dans la conversation
| Référence | Sujet | Décision connue |
|---|---|---|
| Q1 | Nature des sprites | **C** : bâtiments **et** décors |
| Q2 | Mode de construction | **A** : assemblage manuel comme des LEGO |
| Q3 | Perspective | **C** : vue 3/4 |
| Q4 | Organisation verticale | **C** : étages **et** calques indépendants |
| Q5 | Retouche | **C** : éditeur pixel art complet intégré |
| Q6 | Bibliothèque | **C** : permanente + importation à tout moment |
| Q7 | Éditeur pixel art | **C** : création de zéro, animation et outils pour modules compatibles |
| Q8 | Dimensions | **C** : libres, formats standards facultatifs |
| Q9 | Profondeur | **C** : automatique + correction manuelle |
| Q10 | Modification d’une ressource | **C** : au choix instance seule ou toutes les utilisations |
| Q11 | Aimantation | **C** : grille, bords et ancres personnalisées |
| Q12 | Répétition | **C** : duplication, ligne, grille et tracé |
| Q13 | Variantes | **C** : variantes regroupées et création dans Pixel Art |
| Q14 | Manipulation | **C** : guides dynamiques, déplacement précis, Ctrl-glisser, outils contextuels |
| Q15 | Interface | **C** : entièrement modulable avec espaces de travail enregistrables |
| Q16 | Aperçu | **C** : éclairage, ombres, fonds/environnement et simulation résultat Godot |

## Configuration globale rapportée par le récapitulatif de l’échange
- **Nom : Sprite Builder Studio.**
- **Windows 11, Python + PySide6, entièrement local, sans IA intégrée.**
- Dossier initial annoncé : cahier des charges, architecture, interface, plan de développement, tests, décisions (51 annoncées).

## Questions proposées dans le questionnaire Q17–Q46, réponses non récupérées
Ces lignes sont des **questions proposées**, pas des décisions validées :

| Questions | Domaines | Statut |
|---|---|---|
| Q17–Q19 | Projets, sauvegardes, export Godot | Réponse originale inconnue |
| Q20–Q24 | Découpe, transformations, modèles, mesures, assemblage | Réponse originale inconnue |
| Q25–Q28 | Outils pixel art, animation, palettes, retouches | Réponse originale inconnue |
| Q29–Q32 | Classement, import, doublons, actualisation bibliothèque | Réponse originale inconnue |
| Q33–Q35 | Grilles, profondeur, ancres | Réponse originale inconnue (proches de Q8/Q9/Q11) |
| Q36–Q38 | Éclairage, environnements, aperçu Godot | Réponse originale inconnue (Q16 pose une base) |
| Q39–Q41 | Assistance, IA, automatisation | Réponse originale inconnue ; **sans IA intégrée** retenu globalement |
| Q42–Q44 | Interface, thèmes, performance | Réponse originale inconnue (Q15 établit la modularité) |
| Q45–Q46 | Architecture, extensions | Réponse originale inconnue |
| Q47–Q51 | Formulations non disponibles ici | Réponse et intitulé inconnus |

## Propositions provisoires prises pour rendre le dossier exploitable
- Format projet structuré et sauvegarde atomique ; export PNG / JSON puis Godot 4.
- Outils de Pixel Art avancés implémentés par paliers, architecture extensible.
- Bibliothèque SQLite et fichiers copiés ; versionnage, restauration ; raccourcis usuels.
- Calques, étages, ancres et variante restent des concepts distincts.
- **Les propositions ne remplacent pas les réponses Q17–Q51**. Elles constituent des hypothèses raisonnables pour faire démarrer Claude sans bloquer le projet.

## Décisions de conception prises le 5 novembre 2026 (à partir de la relecture du dossier et du kit)
| Réf. | Sujet | Décision retenue |
|---|---|---|
| D-A | Grille 3/4 | Valeurs du kit : 16 px/m, case 32 px, élévation 30° (réglable par projet) |
| D-B | Groupes | Imbriqués, 3 niveaux maximum, cycles interdits |
| D-C | Ordre d'affichage | Étage > calque > Z manuel (0 par défaut) > profondeur auto > insertion. *Corrigé le 5 nov. : la première version plaçait le Z manuel après la profondeur auto, ce qui l'empêchait de forcer un ordre.* |
| D-D | Rotation | Pas de rotation libre ; miroir et échelle entière seulement |
| D-E | Groupe en module | Module composite (liste d'éléments), pas d'image aplatie |
| D-F | Export Godot | `z_index` fixes |
| D-G | Origine des sprites | Kit généré dans **Blender** (rendu 3/4, élévation 30°), fourni avec fiches JSON, normales et émissions |

Ces points sont des décisions de travail : ils restent modifiables, et priment sur les propositions antérieures qu'ils contredisent.

## Résolutions de conflits
1. **Aucune IA intégrée** prévaut sur la proposition Q40-C (assistant IA), qui n’est pas une réponse récupérée.
2. **Construction manuelle** prévaut sur toute idée de générateur automatique de bâtiments.
3. **Vue 3/4** ne signifie ni 3D native ni isométrie stricte ; laisser la grille configurable.
4. Les fonctions avancées mentionnées ici sont des objectifs de produit ; leur présence dans le dossier n’équivaut pas à un état « implémenté ».

## Si le dossier original est retrouvé un jour
Comparer point par point Q17–Q51, puis mettre à jour uniquement les exigences impactées ; préserver le reste du projet et les tests.

## Notes J6 — Prévisualisations et interopérabilité
- **Éclairage = SIMULATION** (bandeau orange dans l'aperçu), jamais écrite dans les sprites : couleur = base × (ambiante + lumière × max(0, N·L)) + émission. Normales lues depuis `_n` (case « inverser le vert » : Blender est Y-haut), émission depuis `_e`. Les variantes réutilisent les cartes de la base.
- Ombres portées : silhouette cisaillée/aplatie sous le pivot, dessinées sous tous les sprites (pas par étage).
- Comparaison avec `kit_village_scene_lumiere.png` : similarité ≈ 0,84 (indicatif seulement : autre taille, autre fond, autre modèle d'éclairage).
- Fonds : préréglages (ciel, herbe, terre, nuit, gris) ; fond du canevas uni, dégradé seulement dans l'aperçu. Pas d'image de référence importée.
- Exports isolés dans `sbs/exporters/` : modèle neutre `ExportScene` (sans Qt), protocole `Exporter.plan()`, `run_export` ne lève jamais. Sécurité : marqueur `.sbs_export.json`, refus d'écraser des fichiers non créés par l'app, chemins `..`/absolus refusés, scène vide refusée, écriture atomique.
- Godot 4 : Node2D par étage et par calque, Sprite2D par objet dans l'ordre de dessin, `centered=false`, `offset=-pivot`, filtre nearest ; masqué → `visible=false` ; verrouillé → `_edit_lock_` ; groupes en métadonnées. Pas d'AnimatedSprite (animations en JSON / spritesheet).
- Validation réelle : test headless avec Godot 4.7.2 (`SBS_GODOT` pour changer le chemin) comparant positions, ordre, transparence, visibilité, filtre.
- Format projet inchangé (v3).

## Notes J7 — Stabilisation / ergonomie
- **Sauvegardes versionnées** (`services/backups.py`) : à chaque enregistrement réussi, copie datée dans `<données>/backups/<id projet>/` (10 gardées par défaut, doublons exacts ignorés, élagage automatique). Une ancienne version s'ouvre comme copie non enregistrée (nouvel identifiant) : le projet courant n'est jamais touché.
- **Récupération après arrêt brutal** : autosave toutes les 2 min (réglable, 0 = désactivée) dans `<données>/recovery/`, seulement si le projet est modifié ; effacée à l'enregistrement et à la fermeture normale. Écritures atomiques en deux fichiers (projet puis fiche). Copie abîmée → renommée `.abimee`, jamais reproposée. Hypothèse : une seule instance de l'application.
- **Import par lot** (`services/batch_import.py`) : PNG copié tel quel ; GIF/BMP/WebP convertis en PNG RGBA (1re image) ; limite 4096 px/côté lue dans l'en-tête avant décodage ; doublon = même SHA-256 d'un module « local » ; pivot au milieu du bas ; erreurs par fichier sans arrêter le lot ; arrière-plan, progression, annulation.
- **Options / raccourcis / espaces de travail** : raccourcis identifiés par menu + libellé (ou nom d'objet pour Annuler/Rétablir), surcharges stockées dans les préférences, conflits refusés avant toute modification ; espaces de travail = états de docks nommés (20 max). Format projet inchangé (v3).
- **Performance** : mesures dans `docs/Performances.md` ; 5 goulots corrigés (requêtes SQLite par objet, images rouvertes, O(n²) à la suppression/annulation). Cache d'images borné à 256 Mo.
- **Paquet** : PyInstaller (dossier) avec deux exécutables (fenêtre / console), `--selftest` et `--version`, scripts `packaging/build_windows.ps1` et `install_test.ps1`. PyInstaller installé hors du Python de l'utilisateur (`pip --target`). Non signé.
- Recette complète : `08_Recette_J7.md`.

## Notes J3 « dimensions libres » (précisé avec l'utilisateur : redimensionner + couvrir une largeur)
- **Redimensionner** (`services/resize.py`, F5) : facteurs entiers uniquement (×2…×8, ÷2…÷4), voisin le plus proche → aucune couleur nouvelle, pixels nets. Réduction refusée si la taille n'est pas divisible. Résultat = NOUVEAU module « local » (l'original n'est jamais modifié, pas de changement du format projet : une instance reste « module + position »). Pivot/ancrages recalculés (centre du bloc ; le dernier pixel et le bord restent au bord) ; mots-clés repris ; variantes et cartes `_n`/`_e` non reprises. Maximum 4096 px.
- **Remplacer la sélection** : une seule commande annulable (`SwapAssets`), pivot inchangé ; un module source utilisé N fois ne crée qu'UN module redimensionné. Les modules créés restent dans la bibliothèque après annulation.
- **Couvrir une longueur** (`domain/repeat.cover`, mode du dialogue Répéter) : « over » / « within » / « exact » ; origine = pivot de la première pièce ; la taille de pièce est une valeur saisie (largeur ou hauteur du module proposée).
- Non fait (hors choix de l'utilisateur) : étirement 9-slice, mise à l'échelle par instance sans créer de module.

## Notes — Perspective (mur qui s'éloigne en diagonale)
- Mode « Mur en perspective » du dialogue Répéter (`domain/repeat.perspective_wall`, `resize.warp_wall_piece/create_wall_piece`, `CanvasScene.place_wall`) : N pièces (≤ 40), échelle linéaire de 100 % à X % (10–100), largeurs proportionnelles à l'échelle moyenne, raccords arrondis une seule fois (bord droit de i = bord gauche de i+1), sol en pente. Chaque pièce est un module déformé colonne par colonne (voisin le plus proche : hauteur et bas de chaque colonne), réutilisé si identique. Les raccords partagent hauteur et point bas : plus d'escalier. Format projet inchangé.
- Ordre : si le bout lointain est plus bas à l'écran que le proche, `z_manual` décroissant est posé pour garder la plus proche devant ; sinon l'ordre automatique (par y) suffit.
- Limites : aperçu en taille normale (positions seulement), variantes et cartes `_n`/`_e` non reprises, réduction non entière → pixels de tailles irrégulières (assumé pour un effet de recul).
