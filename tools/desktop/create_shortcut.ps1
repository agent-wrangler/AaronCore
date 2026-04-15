$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$desktop = [Environment]::GetFolderPath('Desktop')
$userProfile = [Environment]::GetFolderPath('UserProfile')
$shortcutPath = Join-Path $desktop 'AaronCore.lnk'
$packagedTargets = @(
  (Join-Path $userProfile 'AaronCoreDesktop\win-unpacked\AaronCore.exe')
  (Join-Path $userProfile 'NovaCoreDesktop\win-unpacked\AaronCore.exe') # legacy fallback
  (Join-Path $userProfile 'NovaCoreDesktop\win-unpacked\NovaCore.exe') # legacy exe fallback
)
$packagedTarget = $packagedTargets | Where-Object { Test-Path $_ } | Select-Object -First 1
$fallbackTarget = Join-Path $root 'start_nova.bat'
$target = if ($packagedTarget) { $packagedTarget } else { $fallbackTarget }
$iconCandidates = @(
  Join-Path $root 'static\icon\ico-sizes\aaroncore-desktop-multi.ico'
  Join-Path $root 'static\icon\aaroncore-desktop-svg.ico'
  Join-Path $root 'static\icon\aaroncore-desktop-soft.ico'
  Join-Path $root 'static\icon\aaroncore-desktop.ico'
  Join-Path $root 'static\icon\aaroncore.ico'
  Join-Path $root 'static\icon\nova.ico'
)
$icon = $iconCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

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
