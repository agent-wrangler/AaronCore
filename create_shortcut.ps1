$s = (New-Object -COM WScript.Shell).CreateShortcut('C:\Users\36459\Desktop\NovaCore.lnk')
$s.TargetPath = 'C:\Program Files\Python311\python.exe'
$s.Arguments = 'C:\Users\36459\NovaCore\desktop.py'
$s.WorkingDirectory = 'C:\Users\36459\NovaCore'
$s.Description = 'NovaCore AI'
$s.Save()
Write-Host 'created!'
