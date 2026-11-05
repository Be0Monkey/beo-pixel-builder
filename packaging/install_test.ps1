<#
.SYNOPSIS  Test d'installation : copie le paquet dans des dossiers « difficiles » et vérifie qu'il fonctionne.
.EXAMPLE   .\packaging\install_test.ps1
Contrôles : --version ; auto-test complet (--selftest) ; lancement de l'application (hors écran) qui reste
ouverte ; dans un chemin avec accents et espaces, puis dans un chemin très long. Ne touche pas à tes données
(dossier de données temporaire). Code de sortie 0 = tout est bon.
#>
param([string]$Dist = "")
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
if (-not $Dist) { $Dist = "$root\dist\SpriteBuilderStudio" }
if (-not (Test-Path "$Dist\SpriteBuilderStudio-console.exe")) { throw "Paquet introuvable : $Dist (lance d'abord build_windows.ps1)" }
$failures = 0
function Check($name, [bool]$ok, $detail = "") {
    if ($ok) { Write-Host "[OK]    $name $detail" } else { Write-Host "[ECHEC] $name $detail"; $script:failures++ }
}
$base = Join-Path $env:TEMP "SBS install é test"
# Windows refuse de lancer un programme dont le chemin dépasse 260 caractères (limite du système) :
# on teste un chemin long mais valide (≈ 140 caractères pour le dossier).
$long = Join-Path $base (("dossier très long " * 3).Trim() + "\" + ("sous dossier " * 2).Trim())
foreach ($target in @("$base\avec accents et espaces", $long)) {
    Write-Host "--- Emplacement : $target ($($target.Length) caractères)"
    if (Test-Path $base) { Remove-Item $base -Recurse -Force -ErrorAction SilentlyContinue }
    New-Item -ItemType Directory -Force $target | Out-Null
    try { Copy-Item "$Dist\*" $target -Recurse -Force } catch { Check "copie du paquet" $false $_.Exception.Message; continue }
    $cli = "$target\SpriteBuilderStudio-console.exe"; $gui = "$target\SpriteBuilderStudio.exe"
    $data = Join-Path $env:TEMP ("sbs_install_data_" + [guid]::NewGuid().ToString("N"))
    $env:SBS_DATA_DIR = $data; $env:QT_QPA_PLATFORM = "offscreen"; $env:PYTHONIOENCODING = "utf-8"
    $v = & $cli --version 2>&1 | Out-String
    Check "--version" ($v -match "Sprite Builder Studio \d") $v.Trim()
    $report = Join-Path $env:TEMP "sbs_selftest_report.txt"
    $p = Start-Process -FilePath $cli -ArgumentList "--selftest", "--report", "`"$report`"" -PassThru -Wait -WindowStyle Hidden
    $text = if (Test-Path $report) { Get-Content $report -Raw -Encoding UTF8 } else { "" }
    Check "auto-test (--selftest)" ($p.ExitCode -eq 0 -and $text -match "tout fonctionne") "code $($p.ExitCode)"
    if ($p.ExitCode -ne 0) { Write-Host $text }
    $app = Start-Process -FilePath $gui -PassThru -WindowStyle Hidden
    Start-Sleep -Seconds 6
    Check "l'application démarre et reste ouverte" (-not $app.HasExited)
    if (-not $app.HasExited) { Stop-Process -Id $app.Id -Force }
    Remove-Item $data -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item Env:\SBS_DATA_DIR, Env:\QT_QPA_PLATFORM -ErrorAction SilentlyContinue
}
Remove-Item $base -Recurse -Force -ErrorAction SilentlyContinue
if ($failures -eq 0) { Write-Host "INSTALLATION VALIDEE"; exit 0 } else { Write-Host "$failures échec(s)"; exit 1 }
