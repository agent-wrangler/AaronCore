$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$repoPath = $repoRoot.Path.TrimEnd("\")
$commandFile = Join-Path $repoPath "aaron.bat"
$longCommandFile = Join-Path $repoPath "aaroncore.bat"

if (-not (Test-Path -LiteralPath $commandFile)) {
    throw "Cannot find aaron.bat next to the installer. Please run this installer from the AaronCore folder."
}

if (-not (Test-Path -LiteralPath $longCommandFile)) {
    throw "Cannot find aaroncore.bat next to the installer. Please run this installer from the AaronCore folder."
}

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
$parts = @()

if (-not [string]::IsNullOrWhiteSpace($userPath)) {
    $parts = $userPath -split ";" | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
}

$alreadyInstalled = $false
foreach ($part in $parts) {
    try {
        if ((Resolve-Path $part -ErrorAction Stop).Path.TrimEnd("\") -ieq $repoPath) {
            $alreadyInstalled = $true
            break
        }
    } catch {
        if ($part.TrimEnd("\") -ieq $repoPath) {
            $alreadyInstalled = $true
            break
        }
    }
}

if ($alreadyInstalled) {
    Write-Host "AaronCore is already installed for this Windows user." -ForegroundColor Green
} else {
    $newPath = (@($parts) + $repoPath) -join ";"
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    $env:Path = $env:Path + ";" + $repoPath
    Write-Host "AaronCore command installed." -ForegroundColor Green
}

Write-Host ""
Write-Host "Next step:" -ForegroundColor Cyan
Write-Host "  1. Open a new PowerShell window." -ForegroundColor White
Write-Host "  2. Type:" -ForegroundColor White
Write-Host "  aaron" -ForegroundColor White
Write-Host "  or:" -ForegroundColor White
Write-Host "  aaroncore" -ForegroundColor White
