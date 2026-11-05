# Sprite Builder Studio

Application Windows 11 locale (Python + PySide6), **sans IA**, pour assembler à la main des sprites 2D en vue 3/4,
comme avec des briques : bibliothèque (kit Blender ou images à toi), assemblage au pixel près, étages/calques/groupes,
retouche pixel, animations, répétitions, aperçu éclairé (simulation), export PNG / Godot 4 / JSON.

- **Utiliser** : `src/sbs/resources/Guide_utilisateur.md` (aussi dans l'appli : Aide › Guide utilisateur, F1).
- **Spécifications** : `docs/specs/` (commencer par `04_Plan_de_developpement_Claude.md`) ; recette : `docs/specs/08_Recette_J7.md`.
- **Performances mesurées** : `docs/Performances.md`.

## Lancer (développement)
```
pip install -e .[dev]
python -m sbs                # l'application
python -m sbs --version
python -m sbs --selftest     # auto-test d'installation (sans fenêtre visible)
```

## Tester
```
python -m pytest                          # tout (interface hors écran)
$env:SBS_KIT_DIR = "C:\chemin\du\kit"     # + tests sur le vrai kit (T13, T15)
$env:SBS_GODOT   = "C:\chemin\Godot_console.exe"   # + validation réelle de l'export dans Godot 4
python tools/benchmark.py --sizes 1000 5000 20000  # mesures de performance
```

## Construire le paquet Windows
```
pip install pyinstaller
.\packaging\build_windows.ps1        # -> dist\SpriteBuilderStudio\ et un .zip
.\packaging\install_test.ps1         # test d'installation (chemins accentués/espacés/longs, auto-test, démarrage)
```
Le paquet n'est pas signé numériquement : Windows SmartScreen peut afficher un avertissement au premier lancement.

## État
Jalons **J0 à J7** réalisés (voir `docs/specs/06_Decisions_et_tracabilite.md` pour les décisions et les limites connues).
