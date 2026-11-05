# 08 — Recette J7 : passage de `05_Plan_de_tests.md`

Légende : ✅ vérifié automatiquement (nom du test) · 🟡 partiel / indirect · ⬜ non vérifié (à faire à la main).
Résultat de référence : suite complète sur le PC de développement, avec `SBS_KIT_DIR` (vrai kit) et Godot 4.7.2.

## B. Tests unitaires prioritaires
| ID | Statut | Preuve |
|---|---|---|
| T01 | ✅ | `test_project_io::t01_aller_retour_identifiants_positions_ordre` ; `test_demo_complete::s01…` |
| T02 | ✅ | `test_kit_importer::t02_…` ; `test_batch_import::t02_meme_nom_contenus_differents…` |
| T03 | ✅ | `test_floors_groups_gui::t03_grouper_degrouper_et_annulation` |
| T04 | ✅ | `test_history::t04_deplacer_puis_annuler_restaure_exactement` |
| T05 / T06 | ✅ | `test_asset_edit_gui::15_fenetres_detacher_une_puis_modifier_la_source` ; `test_asset_edit::clone_independant` |
| T07 | ✅ | `test_snapping::*` ; `test_asset_edit_gui::aimant_ancrages_pendant_le_glisser` |
| T08 | ✅ | `test_scene_model::t08_ordre_stable_a_profondeur_egale` |
| T09 | ✅ | `test_exporter::t09_un_sprite_exporte_est_identique_a_l_original` |
| T10 | ✅ | `test_floors_groups::t10_migration_v1_vers_v2` ; `test_animation_repeat::projet_v3…migration` ; `test_project_io::t10_t11…` |
| T11 | ✅ | `test_project_io::t10_t11_fichiers_invalides…` ; `test_kit_importer::t11_image_corrompue…` ; `test_batch_import::erreurs_signalees…` |
| T12 | ✅ | `test_backups::t12_ecriture_interrompue_garde_la_derniere_copie_saine` ; `test_session_gui::t12_arret_brutal_puis_recuperation` |
| T13 | ✅ | `test_kit_importer::t13_import_complet` + `kit_reel` (163 modules, avec `SBS_KIT_DIR`) |
| T14 | ✅ | `test_kit_importer::t14_variantes_rattachees_sans_doublon` |
| T15 | ✅ | `test_exporter::recettes_du_kit_identiques_aux_images_de_reference` (avec `SBS_KIT_DIR`) |
| T16 | ✅ | `test_kit_importer::t16_fiche_incomplete` |
| T17 | ✅ | `test_floors_groups::groupes_profondeur_max_et_cycles` ; `test_floors_groups_gui::groupes_imbriques_max_3_niveaux` |

## C. Scénarios de bout en bout
| ID | Statut | Preuve / remarque |
|---|---|---|
| S01 maison simple | ✅ | `test_demo_complete::s01_maison_simple_de_bout_en_bout` (10 éléments, groupe, enregistrer, rouvrir dans une autre fenêtre, export PNG : 0 pixel de différence) |
| S02 maison avec étage | ✅ | `test_floors_groups_gui::s02_etages_masquer_verrouiller_deplacer` |
| S03 fenêtre partagée | ✅ | `test_asset_edit_gui::15_fenetres…` (14 mises à jour, 1 indépendante) |
| S04 perspective 3/4 | ✅ | `test_demo_complete::s04_perspective_3_4_ordre_apres_sauvegarde` |
| S05 pixel art | 🟡 | `test_pixel_gui`, `test_pixel_edit`, `test_pixel_io` (tuile neuve, palette, masque, sauvegarde) ; l'aspect net à 800 % n'a pas été regardé à l'écran |
| S06 animation | ✅ | `test_animation_repeat` (4 images, FPS, planche, rechargement du projet) ; visualisation non regardée à la main |
| S07 répétition | ✅ | `test_repeat_gui` (ligne, grille, tracé ; objets restent éditables) |
| S08 Godot | ✅ | `test_godot_real` (Godot 4.7.2 en arrière-plan : positions, pivots, transparence, ordre, filtre) |

## D. Ergonomie (à valider par une personne)
| Point | Statut | Remarque |
|---|---|---|
| Premier sprite sans tutoriel | ⬜ | Guide intégré (F1) ; non testé avec un nouvel utilisateur |
| Souris suffisante ; clavier = accélérateur | 🟡 | Tout est faisable à la souris/menus ; non chronométré |
| Grilles et aimants visibles et désactivables | ✅ | Barre d'outils + menu ; état dans la barre d'état |
| Aucun panneau perdu après personnalisation | ✅ | `test_session_gui::espaces_de_travail` (disposition cassée → réinitialisation), `test_launch` |
| Fermeture avec modifications | ✅ | `test_project_window::confirmation_avant_de_perdre…` ; récupération après arrêt brutal |

## E. Compatibilité
| Point | Statut | Remarque |
|---|---|---|
| Windows 11 | ✅ | Paquet construit et testé sur le PC de développement (`packaging/install_test.ps1`) |
| Écrans 1920×1080 / 2560×1440, échelles 100/125/150 % | ⬜ | Non testé |
| Noms accentués, espaces | ✅ | Tests unitaires et installation du paquet dans un dossier accentué avec espaces |
| Chemin long | 🟡 | Testé jusqu'à ≈ 140 caractères ; Windows refuse de lancer un programme au-delà de 260 (limite du système, documentée) |
| Dossier d'import en lecture seule | 🟡 | L'import ne fait que lire (`originaux_jamais_modifies`) ; pas de test dédié |
| PNG RGBA, images non carrées, tailles hors norme | ✅ | `test_batch_import`, `test_exporter` |

## F. Charge et performance
Voir `docs/Performances.md` : 1 000 / 5 000 / 20 000 objets mesurés, linéaires ; longue session sans fuite visible ;
import de 1 000 fichiers (`test_batch_import::test_import_de_1000_fichiers…`, arrière-plan avec progression et annulation).
⬜ Non mesuré : vrai rendu à l'écran, PC modeste.

## G. Résilience / sécurité
| Point | Statut | Preuve |
|---|---|---|
| Ressources copiées, originaux intacts | ✅ | `test_kit_importer::originaux_jamais_modifies` ; import d'images : copie |
| Échec d'export : fichier précédent inchangé | ✅ | `test_exporter::echec_d_ecriture…` ; `test_exporters::scene_vide_et_erreurs_disque…` |
| Fichiers Godot existants jamais écrasés | ✅ | `test_exporters::securite_destination` |
| Projet malformé : pas de code exécuté | ✅ | `test_project_io::aucun_code_execute_au_chargement`, `donnees_mal_formees_refusees` |
| Crash pendant l'autosave | ✅ | `test_backups::t12…` ; copie abîmée mise de côté : `test_session_gui::choix_plus_tard_supprimer_et_copie_abimee` |

## Limites connues à la fin de J7
- Pas de signature numérique ni d'installateur (dossier + zip) ; SmartScreen peut avertir.
- Une seule fenêtre de l'application à la fois (la récupération automatique suppose un seul processus).
- L'ergonomie, les échelles d'écran et le rendu réel ne sont pas validés à la main.
- Une seule scène par projet ; l'aperçu éclairé est une simulation ; pas d'AnimatedSprite à l'export Godot.
- « Dimensions libres » (J3) toujours à préciser avec l'utilisateur.
