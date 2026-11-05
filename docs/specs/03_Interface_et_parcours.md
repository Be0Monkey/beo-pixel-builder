# 03 — Interface et parcours utilisateur

## Principes UX
**Construire d’abord.** Les contrôles complexes restent dans les panneaux secondaires ; les actions fréquentes doivent prendre 1–2 gestes. Personnaliser les raccourcis, garder les indications visuelles et ne jamais déclencher une transformation destructive sans retour clair.

## 1. Fenêtre principale (atelier Construction)
```text
┌────────────────────────────────────────────────────────────────────────┐
│ Fichier  Édition  Vue  Construction  Pixel Art  Exporter  Aide        │
│ [Sélection] [Main] [Grille] [Aimants] [Grouper] [Répéter] [Annuler]    │
├──────────────────┬─────────────────────────────┬───────────────────────┤
│ BIBLIOTHÈQUE     │ CANEVAS                     │ PROPRIÉTÉS            │
│ Recherche        │                             │ Position / Pivot      │
│ Catégories       │  Construction en vue 3/4     │ Taille / Rotation     │
│ Miniatures       │                             │ Aimants / Ancrages    │
│ Favoris          │                             ├───────────────────────┤
│ Importer         │                             │ ÉTAGES / CALQUES      │
│                  │                             │ 👁 Toit               │
│                  │                             │ 👁 Étage 1            │
│                  │                             │ 👁 RDC                │
├──────────────────┴─────────────────────────────┴───────────────────────┤
│ X: 120  Y: 80 | Zoom: 200 % | Aimant: Grille+Ancrages | Auto-Z: ON     │
└────────────────────────────────────────────────────────────────────────┘
```
Panneaux dockables, état mémorisé par espace de travail. Une bibliothèque avec **miniatures assez grandes** et recherche utilisable au clavier ; un canevas qui garde le focus sur l’objet manipulé.

## 2. Gestes par défaut
| Action | Geste conseillé |
|---|---|
| Sélectionner / déplacer | Clic gauche / glisser |
| Sélection multiple | Shift + clic ou rectangle de sélection |
| Panoramique | Bouton central glisser ; outil Main alternatif |
| Zoom | Molette (si conflit avec défilement panneaux, seulement au-dessus du canevas) |
| Dupliquer | Ctrl+D ; Ctrl + glisser |
| Supprimer | Suppr |
| Annuler / refaire | Ctrl+Z / Ctrl+Y |
| Déplacement précis | Flèches ; Shift+flèches = pas configurable |
| Contextuel | Clic droit sur l’élément |
| Ajustement sans aimant | Alt pendant le glisser (configurable) |

**Remarque :** raccourcis à exposer dans Préférences ; éviter les conflits Windows / éditeur pixel art.

## 3. Parcours : premier bâtiment en cinq minutes
1. Créer projet et choisir « Nouvelle construction » ; un canevas s’ouvre.
2. Importer un dossier de sprites (ou glisser quelques PNG) ; les miniatures arrivent dans une catégorie choisie.
3. Glisser un mur puis un angle, activer aimantation et placer la porte.
4. Ajouter un étage et un calque « Toit » ; déplacer le toit devant/derrière jusqu’au bon chevauchement.
5. Grouper la construction ; sauvegarder ; exporter PNG transparent.

## 3 bis. Premier lancement avec le kit
Au premier lancement, proposer « Importer le kit de sprites » (choix du dossier). Progression visible ; les 163 modules arrivent classés dans leurs 15 catégories, avec leurs variantes. Les 18 recettes apparaissent comme modules composites prêts à glisser sur le canevas.

## 4. Modifier un module placé
- Double-clic / menu **Éditer le sprite** ouvre atelier Pixel Art avec ce module.
- Action d’édition explicitement choisie : **cette instance seulement** ou **toutes les utilisations de la ressource**.
- Pour l’édition locale, créer une copie liée uniquement à l’instance ; pour l’édition globale, afficher le nombre d’utilisations affectées.
- Retour dans Construction avec actualisation du rendu ; annulation possible.

## 5. Atelier Pixel Art
Disposition : outils (gauche), image agrandie au centre, palette et calques (droite), timeline (bas si animation). Outils contextuels de points d’ancrage et édition de pixels **séparés** afin qu’un dessin ne déplace pas accidentellement une ancre.

## 6. Parcours : modules compatibles
1. Ouvrir deux sprites dans Pixel Art ou bibliothèque.
2. Définir pivot et points nommés (par ex. `mur_haut`, `toit_bas`). Pour les modules du kit, le pivot est déjà fourni (`ancrage_px`) ; les points nommés sont à ajouter.
3. Configurer les types de connexion compatibles.
4. Dans Construction, déplacer le toit : affichage des points compatibles et capture à proximité.
5. Forcer l’alignement manuel si la vue 3/4 nécessite une exception.

## 7. États et messages
- Modification non sauvegardée : pastille dans titre, confirmation avant fermeture.
- Images manquantes : placeholders clairs et proposition de relier un fichier.
- Import long : barre de progression et annulation ; jamais de fenêtre figée.
- Valeurs numériques validées : pas de coordonnées NaN / infinis ; taille nulle refusée ; expliquer le problème dans le champ.
- Annulation/rétablissement : indication du nom de la dernière commande.

## 8. Prévisualisation
Onglet d’aperçu avec choix : damier, fond coloré, image de référence, environnement composé ; commandes d’éclairage facultatives. **Ne pas confondre** aperçus d’ombres simulées et éclairage réel de Godot. Bouton « Comparer avant/après » utile pour les variantes.

## 9. Espaces de travail
Construction ; Décors ; Pixel Art ; Animation. Les dispositions sont des presets modifiables ; enregistrer/restaurer la disposition de l’utilisateur. Remettre les panneaux par défaut si l’un devient inaccessible.

## 10. Accessibilité et confort
Tailles de panneaux et miniatures réglables, contrastes suffisants, icônes accompagnées de libellés/infobulles, actions accessibles sans drag-only, support DPI et périphériques de pointage usuels.
