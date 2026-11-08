# Liste des modifications — Sprite Builder Studio

Document vivant : on y ajoute les idées, on coche ce qui est fait. Dernière mise à jour : 8 novembre 2026.
Légende : ☐ à faire · ☑ fait · Taille : S (rapide), M (une séance), L (gros chantier).

## À faire en priorité (les 4 étapes retenues)

| # | Étape | Où | Taille | État |
|---|-------|----|--------|------|
| 1 | Remplacer une couleur par une autre dans tout le sprite | Dessiner (web ✔, PC ✔) | S | ☑ |
| 2 | Rampes de couleurs : nuances plus sombre / plus claire d'une couleur choisie | Dessiner (web) | S | ☑ |
| 3 | Miroir horizontal d'un objet + alignement automatique (aligner, centrer, répartir) | Assembler (web ✔, PC à faire) | M | ☑ web |
| 4 | Regénérer le zip Windows + publier une release GitHub | PC / diffusion | S | ☐ |

## Priorité réelle : proches sur PC + tablette graphique sans écran (8 nov.)

Contexte : pas encore testé par des proches. Public visé = PC, tablette sans écran (on regarde l'écran, on dessine sur la tablette). Parcours : dessiner des sprites, puis les assembler.

- ☐ Installation sans accroc : zip à jour, notice d'une page, parcours complet vérifié par nous (étape 4 passe en premier).
- ☑ (existait déjà : pixel survolé surligné) Curseur bien visible sur le canvas : pixel survolé surligné + aperçu du pinceau, car sans écran sur la tablette on ne voit pas où est le stylet.
- ☑ Tracé : lissage du trait (stabilisateur), mode « pixel parfait » (pas de coins doublés), ligne droite avec Maj.
- ☑ Gomme : bout gomme du stylet reconnu comme gomme (existait déjà dans la version web).
- ☑ Raccourcis clavier complets et listés (touche ?) (touches de tablette configurables : annuler, pipette, outil, zoom, panoramique) — dans le guide.
- ☐ Zoom / déplacement au clavier + molette (la tablette a peu de place pour les gestes).
- ☑ Boucle rapide dessiner → assembler (Ctrl+Entrée) : une touche pour envoyer le sprite aux modules et le poser aussitôt dans la scène.
- ☐ Aperçu du sprite en contexte (sur herbe / sol, à côté d'un autre module) pendant qu'on dessine.
- ☐ Vérifier sur une vraie tablette (Windows Ink, mapping de la zone de travail) avant de la présenter aux proches.
- ☐ Fiche de test pour les proches : « ce qui m'a bloqué » à chaque étape.

## Simplifier (moins de boutons, moins d'étapes)

- ☐ Regrouper les actions rares d'un objet dans un menu « Plus… » (Objet : ordre, groupe, dupliquer, modifier, supprimer).
- ☐ Un seul bouton « Enregistrer » dans Dessiner qui propose : mettre à jour le module ou créer un module (au lieu de « → Mes modules » + « Mettre à jour »).
- ☐ Mode simple / mode complet : cacher Calques, Étages, Animations tant qu'on n'en a pas besoin.
- ☐ Écran d'accueil de 4 étapes au premier lancement (choisir, poser, déplacer, envoyer au PC).
- ☐ Scène d'exemple déjà montée, à modifier pour comprendre.
- ☐ Bouton « Annuler » toujours visible sur téléphone (pas seulement au clavier).

## Qualité de vie

- ☐ Dessiner : aperçu du sprite sur de l'herbe / sable / sol avant de valider.
- ☐ Dessiner : palette extraite d'une image de référence ; palettes enregistrées avec un nom ; mode « palette verrouillée ».
- ☐ Dessiner : rotation par 90°, décalage des pixels (tuiles), ombre portée automatique.
- ☐ Assembler : cacher un objet précis (sans passer par un calque).
- ☐ Assembler : liste des dernières actions pour revenir à un point précis.
- ☐ Modules : collections nommées (« village », « donjon »), recherche par couleur dominante ou par taille.
- ☐ Avertir avant de quitter si la scène n'a pas été envoyée au PC.
- ☐ Copier-coller de couleurs entre sprites (pipette sur une autre fenêtre).

## Ergonomie téléphone

- ☐ Loupe de précision (appui long) pour poser au pixel près.
- ☐ Bannière « Ajouter à l'écran d'accueil » avec les étapes iPhone / Android.
- ☐ Barre d'outils flottante au pouce (outils principaux en bas de l'écran).
- ☐ Vérifier toutes les tailles de boutons au doigt (44 px) dans Dessiner.

## Échange téléphone ↔ PC

- ☐ Variantes et aperçu éclairé sur le téléphone (paquet de modules plus lourd).
- ☐ Inclure les versions de scène dans la sauvegarde complète.
- ☐ Envoi sans fichier (code à scanner) — gros chantier, demande un petit serveur.

## Diffusion

- ☐ Release GitHub avec le zip Windows (voir étape 4).
- ☐ Signature du programme Windows pour supprimer l'avertissement SmartScreen (payant, à décider selon le nombre d'utilisateurs).

## Idées en plus (discussion du 8 nov., pas encore triées)

Dessiner
- ☐ Onion skin : voir en transparence l'image précédente / suivante d'une animation pendant qu'on dessine.
- ☐ Grille d'aide réglable (cases de 8 / 16 px), repères au centre et au pivot du module.
- ☐ Afficher le point d'appui (pivot) directement dans Dessiner et pouvoir le déplacer là.
- ☐ Sélection : déplacer, retourner, pivoter, copier un morceau du sprite.
- ☐ Palette « jeu » : couleurs groupées par matériau (herbe, bois, pierre) avec leurs nuances.
- ☐ Historique visuel : miniatures des derniers états pour revenir en arrière.
- ☐ Taille de toile prédéfinie (16, 32, 48, 64). ☑ « Recadrer au contenu » fait.

Assembler
- ☐ Aimantation aux bords des autres modules (poser un mur contre un mur sans trou ni chevauchement).
- ☐ Pot de peinture pour modules : poser un même module sur toute une zone dessinée (herbe, sol).
- ☐ Règle / mesure entre deux objets, affichage des coordonnées au survol.
- ☐ Fond de scène réglable (couleur, damier, image de référence) pour juger le rendu.
- ☐ Verrouiller un objet ou un calque pour ne pas le déplacer par erreur (existe pour les calques, à rendre plus visible).
- ☐ Rechercher un objet dans la scène par son nom de module.

Confort général
- ☐ Thème clair / sombre / suivre le système, au choix.
- ☐ Taille de l'interface réglable (petite / normale / grande) pour les écrans différents.
- ☑ Aide intégrée : touche ? (fait) ; ☐ bulles d'aide sur chaque outil.
- ☐ Messages d'erreur qui disent quoi faire (et pas seulement ce qui ne va pas).
- ☑ Sauvegarde automatique visible (« enregistré à 16:02 »), pour rassurer.
- ☐ Récupération après plantage : proposer de rouvrir le dernier travail.
- ☐ Langue : anglais en plus du français, si l'appli sort du cercle de proches.

Équipe / partage
- ☐ Exporter une feuille de sprites (planche PNG + fichier de positions) pour les moteurs de jeu.
- ☐ Importer une feuille de sprites existante et la découper en modules.
- ☐ Partager un lot de modules entre deux personnes (pack à envoyer, sans toucher au reste de la bibliothèque).

## Questions ouvertes (à trancher ensemble)

- ☐ Quelles idées supprimer parce qu'elles ne servent pas ?
- ☐ Lesquelles sont indispensables avant de montrer l'appli aux proches ?
- ☐ Quels petits agacements ou oublis à ajouter ?
- ☐ Lissage du trait : simple interrupteur (éteint par défaut) puis réglage 0-10 plus tard ?
- ☐ Mode simple / mode complet : cacher calques, étages et animations tant qu'on n'en a pas besoin ?
- ☐ Quelle tablette pour les proches (sans écran confirmé) ? Pas de tablette de test de notre côté : on passe par leurs retours.

## Déjà fait (historique)

- ☑ Édition web : étages, calques, groupes, sélection multiple.
- ☑ Répéter : grille, couvrir une longueur, le long d'un tracé, mur en perspective (avec aperçu avant validation et réglages mémorisés).
- ☑ Animations, exports (PNG, Godot, JSON), plusieurs scènes, versions horodatées de la scène.
- ☑ Raccourcis clavier, copier-coller entre scènes, favoris et récents, sauvegarde / restauration complète, panneau repliable sur téléphone, gros boutons tactiles.
- ☑ Masquer / démasquer des modules ; modifier un module avec Dessiner.
- ☑ Palette de couleurs : 3 palettes (elfvsorc, kit, base du PC), récentes, code couleur, retirer des couleurs.
- ☑ Une seule appli (PC + web), modules de départ intégrés, accès depuis le téléphone.

## Idées à trier (à compléter ensemble)

- _(vide pour l'instant — dis-moi ce qui te gêne à l'usage et je l'ajoute ici)_
