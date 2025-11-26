param(
    [string]$BatFile = "$PSScriptRoot\run_monitor.bat",
    [string]$ShortcutName = "Monitor Encoder.lnk",
    [string]$IconFile = "$PSScriptRoot\utils\icono.ico",
    [string]$DestinationFolder = "$PSScriptRoot"  # por defecto crear en la carpeta del proyecto
)

if (-not (Test-Path $BatFile)) {
    Write-Error "No se encontró el .bat: $BatFile"
    exit 1
}

$WshShell = New-Object -ComObject WScript.Shell
$ShortcutPath = Join-Path -Path $DestinationFolder -ChildPath $ShortcutName
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)

# Asegurarse que la ruta sea absoluta (se obtiene del script root)
$absBat = (Resolve-Path $BatFile).Path
$absIcon = if (Test-Path $IconFile) { (Resolve-Path $IconFile).Path } else { $null }

$Shortcut.TargetPath = $absBat
$Shortcut.WorkingDirectory = Split-Path $absBat
$Shortcut.WindowStyle = 1
if ($absIcon) { $Shortcut.IconLocation = $absIcon }
$Shortcut.Save()

Write-Host "✅ Acceso directo creado en: $ShortcutPath"
