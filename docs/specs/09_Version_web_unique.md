# Une seule application : Sprite Builder Studio (web + PC)

**Décision (6 nov. 2026)** : Sprite Builder Studio est UNE appli, avec deux éditions qui partagent le même dépôt, les mêmes modules de départ et le même format d'échange.
- **Édition web** (`atelier-pixel/`, page unique, installable sur téléphone, tablette et PC, aucun téléchargement) : c'est l'édition que tout proche peut utiliser. Les modules de départ (`modules-depart.json`, 173 modules) se chargent seuls à la première ouverture.
- **Édition Windows** (`src/sbs`, Python + PySide6) : l'édition de référence. Elle embarque les mêmes modules (`src/sbs/resources/modules_depart.sbspack.json`, installés au premier lancement).
- Les fonctions du PC sont portées sur l'édition web par étapes. Rien n'est retiré de l'édition Windows.

## État du portage (✔ fait, ○ à faire)
| Fonction | Web |
|---|---|
| Dessin au pixel, calques, palette, export PNG / projet | ✔ |
| Bibliothèque de modules (recherche, catégories, import) | ✔ |
| Pose, déplacement, sélection, annuler / rétablir, aimant, grille, zoom | ✔ |
| Ordre devant / derrière, dupliquer, supprimer, point d'appui | ✔ |
| Répéter en ligne / grille | ✔ |
| Redimensionner (×2 à ×4, ÷2, ÷3, nouveau module) | ✔ |
| Envoi de la scène au PC (paquet scène) | ✔ |
| Étages / calques de scène / groupes / multi-sélection | ✔ |
| Répéter le long d'un tracé, couvrir une longueur, mur en perspective | ✔ |
| Variantes, cartes de normales, aperçu éclairé | ○ |
| Animations (images, durée, boucle, aperçu) | ✔ |
| Export PNG de la scène, export Godot / JSON | ✔ |
| Sauvegarde de plusieurs scènes | ✔ |
| Versions / sauvegardes horodatées | ○ |
