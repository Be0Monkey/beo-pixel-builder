<#
.SYNOPSIS  Construit le paquet Windows (dossier autonome + zip) avec PyInstaller.
.EXAMPLE   .\packaging\build_windows.ps1
.EXAMPLE   .\packaging\build_windows.ps1 -Tools D:\beostudio\buildtools   # PyInstaller installé dans un dossier à part
Prérequis : Python 3.12+, `pip install PySide6 Pillow numpy` et PyInstaller (`pip install pyinstaller`).
#>
param([string]$Python = "python", [string]$Tools = "")
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
if ($Tools) { $env:PYTHONPATH = $Tools }
$version = (& $Python -c "import sys; sys.path.insert(0,'src'); import sbs; print(sbs.__version__)").Trim()
Write-Host "Construction de Sprite Builder Studio $version ..."
& $Python -m PyInstaller --noconfirm --clean --distpath "$root\dist" --workpath "$root\build" "$root\packaging\sbs.spec"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller a échoué (code $LASTEXITCODE)" }
$out = "$root\dist\SpriteBuilderStudio"
Copy-Item "$root\src\sbs\resources\Guide_utilisateur.md" "$out\Guide_utilisateur.md" -Force
if (Test-Path "$root\docs\Performances.md") { Copy-Item "$root\docs\Performances.md" "$out\Performances.md" -Force }
$zip = "$root\dist\SpriteBuilderStudio-$version-win64.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path "$out\*" -DestinationPath $zip
$mb = [math]::Round((Get-ChildItem $out -Recurse | Measure-Object Length -Sum).Sum / 1MB, 1)
Write-Host "OK : $out ($mb Mo) et $zip"
