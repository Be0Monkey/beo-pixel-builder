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

## Notes J3a (modules)
- Pivot et ancrages nommés éditables (F4 : Propriétés du module). Portée au choix : toutes les utilisations (source, annulable) ou sélection seulement (copie de la ressource, origine « local »).
- Changer le pivot de la source déplace visuellement les sprites (la position d'une instance est celle de son pivot).
- Bibliothèque v2 (colonne ancrages, migration automatique).

