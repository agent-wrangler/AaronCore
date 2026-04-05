$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$desktop = [Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktop 'AaronCore.lnk'
$packagedTargets = @(
  'C:\Users\36459\AaronCoreDesktop\win-unpacked\AaronCore.exe'
  'C:\Users\36459\NovaCoreDesktop\win-unpacked\AaronCore.exe'
  'C:\Users\36459\NovaCoreDesktop\win-unpacked\NovaCore.exe'
)
$packagedTarget = $packagedTargets | Where-Object { Test-Path $_ } | Select-Object -First 1
$fallbackTarget = Join-Path $root 'start_nova.bat'
$target = if ($packagedTarget) { $packagedTarget } else { $fallbackTarget }
$icon = Join-Path $root 'static\icon\nova.ico'

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $target
$shortcut.Arguments = ''
$shortcut.WorkingDirectory = if ($packagedTarget) { Split-Path -Parent $packagedTarget } else { $root }
$shortcut.Description = 'AaronCore Desktop'
if (Test-Path $icon) {
  $shortcut.IconLocation = "$icon,0"
}
$shortcut.Save()

Write-Host "created: $shortcutPath"
