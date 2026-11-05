# Sprite Builder Studio — Dossier de reconstitution

**Édition :** 5 novembre 2026 (v2) — reconstitution à partir des informations encore accessibles, mise à jour avec le kit de sprites Blender et les décisions D-A à D-G.

## Objet
Sprite Builder Studio est une application **Windows 11, locale, développée en Python avec PySide6**, destinée à assembler manuellement des sprites 2D en **vue 3/4** pour produire bâtiments, décors, modules et animations réutilisables notamment dans Godot.

**Pas d’IA intégrée** dans la configuration retenue. Aucun accès à un service distant n’est nécessaire.

## Contenu
1. `01_Cahier_des_charges.md` — fonctionnalités et exigences fonctionnelles.
2. `02_Architecture_technique.md` — architecture, modèle de données et formats.
3. `03_Interface_et_parcours.md` — ergonomie, écrans, interactions.
4. `04_Plan_de_developpement_Claude.md` — jalons, ordre de réalisation, critères de livraison et consignes à Claude.
5. `05_Plan_de_tests.md` — tests fonctionnels, visuels, robustesse et acceptation.
6. `06_Decisions_et_tracabilite.md` — décisions établies, propositions de conception et points non récupérés.
7. `07_Kit_de_sprites.md` — description du kit de sprites fourni (Blender) : dossiers, fiches JSON, recettes, normales.

## IMPORTANT — provenance
Le ZIP original généré sur téléphone **n’a pas été récupéré**. Ce dossier est une **reconstitution**, pas une copie mot pour mot. Les choix **Q1–Q16** sont directement documentés par la conversation disponible. Les décisions **Q17–Q51** ne sont pas toutes récupérables individuellement. La configuration globale (Windows/PySide6/local/sans IA) provient du récapitulatif de notre échange. Pour les points non confirmés, les documents proposent des valeurs de travail clairement identifiées comme telles, **sans les présenter comme des choix validés**.

## Pour démarrer
Donner le dossier entier à Claude Code / Claude Desktop et commencer par `04_Plan_de_developpement_Claude.md`. Exiger un développement progressif, avec tests de non-régression. **Ne pas implémenter d’emblée toutes les fonctionnalités avancées.**
