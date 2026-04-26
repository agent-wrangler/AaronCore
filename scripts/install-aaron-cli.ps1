$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$repoPath = $repoRoot.Path.TrimEnd("\")
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
    Write-Host "AaronCore CLI is already on your user PATH." -ForegroundColor Green
} else {
    $newPath = (@($parts) + $repoPath) -join ";"
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    $env:Path = $env:Path + ";" + $repoPath
    Write-Host "AaronCore CLI added to your user PATH." -ForegroundColor Green
}

Write-Host ""
Write-Host "Open a new terminal and run:" -ForegroundColor Cyan
Write-Host "  aaron" -ForegroundColor White
