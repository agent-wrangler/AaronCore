$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$repoPath = $repoRoot.Path.TrimEnd("\")
$commandFile = Join-Path $repoPath "aaron.bat"
$longCommandFile = Join-Path $repoPath "aaroncore.bat"
$venvDir = Join-Path $repoPath ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"
$requirementsFile = Join-Path $repoPath "requirements-cli.txt"

function Get-PythonCommand {
    $candidates = @(
        @{ File = "py"; Args = @("-3.11") },
        @{ File = "py"; Args = @("-3") },
        @{ File = "python"; Args = @() },
        @{ File = "python3"; Args = @() }
    )

    foreach ($candidate in $candidates) {
        if (-not (Get-Command $candidate.File -ErrorAction SilentlyContinue)) {
            continue
        }

        try {
            $probeArgs = @($candidate.Args) + @("-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
            $versionText = (& $candidate.File @probeArgs 2>$null | Select-Object -First 1)
            if ($versionText -match "^(\d+)\.(\d+)") {
                $major = [int]$Matches[1]
                $minor = [int]$Matches[2]
                if ($major -gt 3 -or ($major -eq 3 -and $minor -ge 11)) {
                    return $candidate
                }
            }
        } catch {
            continue
        }
    }

    throw "Python 3.11+ was not found. Install Python first, then run this installer again."
}

if (-not (Test-Path -LiteralPath $commandFile)) {
    throw "Cannot find aaron.bat next to the installer. Please run this installer from the AaronCore folder."
}

if (-not (Test-Path -LiteralPath $longCommandFile)) {
    throw "Cannot find aaroncore.bat next to the installer. Please run this installer from the AaronCore folder."
}

if (-not (Test-Path -LiteralPath $requirementsFile)) {
    throw "Cannot find requirements-cli.txt next to the installer. Please run this installer from the AaronCore folder."
}

if (-not (Test-Path -LiteralPath $venvPython)) {
    $pythonCommand = Get-PythonCommand
    Write-Host "Creating local Python environment..." -ForegroundColor White
    $venvArgs = @($pythonCommand.Args) + @("-m", "venv", $venvDir)
    & $pythonCommand.File @venvArgs
}

Write-Host "Installing AaronCore CLI dependencies..." -ForegroundColor White
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r $requirementsFile

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
