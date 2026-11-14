<#
.SYNOPSIS
Crée les raccourcis Windows de NeuroPlanner (Bureau + menu Démarrer).

.DESCRIPTION
Le raccourci lance l'application sans fenêtre de console et prend l'icône livrée
avec le paquet (assets\neuroplanner.ico). Il pointe vers le lanceur installé
(``neuroplanner-gui.exe``) quand il existe, sinon vers ``pythonw.exe -m neuroplanner``.

Idempotent : relancer le script met simplement le raccourci à jour.

.PARAMETER Python
Interpréteur à utiliser (chemin vers python.exe ou pythonw.exe). Par défaut,
celui de la commande ``python`` du PATH.

.PARAMETER NoStartMenu
Ne crée que le raccourci du Bureau.

.EXAMPLE
powershell -ExecutionPolicy Bypass -File scripts\create_shortcut.ps1

.EXAMPLE
powershell -ExecutionPolicy Bypass -File scripts\create_shortcut.ps1 -Python .venv\Scripts\python.exe
#>
[CmdletBinding()]
param(
    [string]$Python = "",
    [switch]$NoStartMenu
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$icon = Join-Path $root "neuroplanner\assets\neuroplanner.ico"
if (-not (Test-Path -LiteralPath $icon)) {
    throw "Icône introuvable : $icon"
}

function Resolve-Launcher {
    param([string]$PythonPath)

    if ($PythonPath) {
        $exe = (Resolve-Path -LiteralPath $PythonPath).Path
        $pythonw = Join-Path (Split-Path -Parent $exe) "pythonw.exe"
        if (Test-Path -LiteralPath $pythonw) { $exe = $pythonw }
        return @{ Target = $exe; Arguments = "-m neuroplanner" }
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) { throw "python introuvable dans le PATH : préciser -Python." }

    $scripts = (& $python.Source -c "import sysconfig; print(sysconfig.get_path('scripts'))").Trim()
    $gui = Join-Path $scripts "neuroplanner-gui.exe"
    if (Test-Path -LiteralPath $gui) {
        # Lanceur sans console installé par « pip install -e . » : aucun argument.
        return @{ Target = $gui; Arguments = "" }
    }

    $pythonw = Join-Path (Split-Path -Parent $python.Source) "pythonw.exe"
    if (Test-Path -LiteralPath $pythonw) {
        return @{ Target = $pythonw; Arguments = "-m neuroplanner" }
    }
    return @{ Target = $python.Source; Arguments = "-m neuroplanner" }
}

function New-NeuroPlannerShortcut {
    param([string]$Path, [hashtable]$Launcher)

    $shell = New-Object -ComObject WScript.Shell
    $link = $shell.CreateShortcut($Path)
    $link.TargetPath = $Launcher.Target
    $link.Arguments = $Launcher.Arguments
    $link.WorkingDirectory = $root
    $link.IconLocation = "$icon,0"
    $link.Description = "NeuroPlanner - suivi d'apprentissage 5 h/jour"
    $link.WindowStyle = 1
    $link.Save()
    Write-Host "  créé : $Path"
}

$launcher = Resolve-Launcher -PythonPath $Python
Write-Host "Cible : $($launcher.Target) $($launcher.Arguments)"

$desktop = Join-Path ([Environment]::GetFolderPath("Desktop")) "NeuroPlanner.lnk"
New-NeuroPlannerShortcut -Path $desktop -Launcher $launcher

if (-not $NoStartMenu) {
    $programs = Join-Path ([Environment]::GetFolderPath("Programs")) "NeuroPlanner.lnk"
    New-NeuroPlannerShortcut -Path $programs -Launcher $launcher
}

Write-Host ""
Write-Host "Termine. Double-clique sur « NeuroPlanner » pour lancer l'application."
Write-Host "Astuce : clic droit sur le raccourci > Epingler a la barre des taches."
