$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$desktop = [Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktop 'NovaCore.lnk'
$packagedTarget = 'C:\Users\36459\NovaCoreDesktop\win-unpacked\NovaCore.exe'
$fallbackTarget = Join-Path $root 'start_nova.bat'
$target = if (Test-Path $packagedTarget) { $packagedTarget } else { $fallbackTarget }
$icon = Join-Path $root 'static\icon\nova.ico'

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $target
$shortcut.Arguments = ''
$shortcut.WorkingDirectory = if (Test-Path $packagedTarget) { Split-Path -Parent $packagedTarget } else { $root }
$shortcut.Description = 'NovaCore Desktop'
if (Test-Path $icon) {
  $shortcut.IconLocation = "$icon,0"
}
$shortcut.Save()

Write-Host "created: $shortcutPath"
