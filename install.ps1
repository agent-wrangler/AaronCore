$ErrorActionPreference = "Stop"

$Repo = "agent-wrangler/AaronCore"
$Branch = "master"
$InstallRoot = Join-Path $env:LOCALAPPDATA "AaronCore"
$AppDir = Join-Path $InstallRoot "app"
$DataDir = Join-Path $InstallRoot "data"
$VenvDir = Join-Path $InstallRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$TempRoot = Join-Path ([IO.Path]::GetTempPath()) ("AaronCoreInstall-" + [guid]::NewGuid().ToString("N"))
$ZipPath = Join-Path $TempRoot "AaronCore.zip"
$ArchiveUrl = "https://codeload.github.com/$Repo/zip/refs/heads/$Branch"

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

    throw "Python 3.11+ was not found. Install Python first, then run this command again."
}

function Add-UserPath {
    param([string]$PathToAdd)

    $current = [Environment]::GetEnvironmentVariable("Path", "User")
    $parts = @()
    if (-not [string]::IsNullOrWhiteSpace($current)) {
        $parts = $current -split ";" | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    }

    foreach ($part in $parts) {
        try {
            if ((Resolve-Path $part -ErrorAction Stop).Path.TrimEnd("\") -ieq $PathToAdd.TrimEnd("\")) {
                return $false
            }
        } catch {
            if ($part.TrimEnd("\") -ieq $PathToAdd.TrimEnd("\")) {
                return $false
            }
        }
    }

    $newPath = (@($parts) + $PathToAdd) -join ";"
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    $env:Path = $env:Path + ";" + $PathToAdd
    return $true
}

function Copy-IfMissing {
    param(
        [string]$Source,
        [string]$Destination
    )

    if ((Test-Path -LiteralPath $Source) -and -not (Test-Path -LiteralPath $Destination)) {
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Destination) | Out-Null
        Copy-Item -LiteralPath $Source -Destination $Destination -Recurse -Force
    }
}

Write-Host ""
Write-Host "AaronCore installer" -ForegroundColor Cyan
Write-Host "Downloading latest AaronCore CLI..." -ForegroundColor White

New-Item -ItemType Directory -Force -Path $TempRoot | Out-Null
New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
New-Item -ItemType Directory -Force -Path $DataDir | Out-Null

try {
    $pythonCommand = Get-PythonCommand
    Invoke-WebRequest -Uri $ArchiveUrl -OutFile $ZipPath -UseBasicParsing
    Expand-Archive -LiteralPath $ZipPath -DestinationPath $TempRoot -Force

    $extracted = Get-ChildItem -LiteralPath $TempRoot -Directory |
        Where-Object { $_.Name -like "AaronCore-*" } |
        Select-Object -First 1

    if (-not $extracted) {
        throw "Downloaded archive did not contain an AaronCore folder."
    }

    $backup = ""
    if (Test-Path -LiteralPath $AppDir) {
        $backup = Join-Path $InstallRoot ("app.backup." + (Get-Date -Format "yyyyMMddHHmmss"))
        Move-Item -LiteralPath $AppDir -Destination $backup
        Write-Host "Previous install backed up to: $backup" -ForegroundColor DarkGray
    }

    Move-Item -LiteralPath $extracted.FullName -Destination $AppDir

    foreach ($required in @("aaron.bat", "aaroncore.bat", "aaron.py")) {
        $requiredPath = Join-Path $AppDir $required
        if (-not (Test-Path -LiteralPath $requiredPath)) {
            throw "Install is incomplete. Missing $required."
        }
    }

    if ($backup) {
        Copy-IfMissing -Source (Join-Path $backup "state_data") -Destination (Join-Path $DataDir "state_data")
        Copy-IfMissing -Source (Join-Path $backup "brain\llm_config.local.json") -Destination (Join-Path $DataDir "brain\llm_config.local.json")
    }

    New-Item -ItemType File -Force -Path (Join-Path $AppDir ".aaroncore-installed") | Out-Null

    if (-not (Test-Path -LiteralPath $VenvPython)) {
        Write-Host "Creating local Python environment..." -ForegroundColor White
        $venvArgs = @($pythonCommand.Args) + @("-m", "venv", $VenvDir)
        & $pythonCommand.File @venvArgs
    }

    Write-Host "Installing AaronCore CLI dependencies..." -ForegroundColor White
    & $VenvPython -m pip install --upgrade pip
    $requirementsFile = Join-Path $AppDir "requirements-cli.txt"
    if (Test-Path -LiteralPath $requirementsFile) {
        & $VenvPython -m pip install -r $requirementsFile
    } else {
        throw "Install is incomplete. Missing requirements-cli.txt."
    }

    $changedPath = Add-UserPath -PathToAdd $AppDir
    if ($changedPath) {
        Write-Host "Installed the aaron and aaroncore commands." -ForegroundColor Green
    } else {
        Write-Host "AaronCore commands were already installed." -ForegroundColor Green
    }

    try {
        $pythonVersion = (& $VenvPython --version 2>&1)
        Write-Host "Python: $pythonVersion" -ForegroundColor DarkGray
    } catch {
        Write-Host "Python was not found. Please install Python 3.11+ before starting AaronCore." -ForegroundColor Yellow
    }

    Write-Host ""
    Write-Host "Next step:" -ForegroundColor Cyan
    Write-Host "  1. Open a new PowerShell window." -ForegroundColor White
    Write-Host "  2. Type:" -ForegroundColor White
    Write-Host "     aaroncore" -ForegroundColor White
    Write-Host "  3. If AaronCore asks for model setup, run:" -ForegroundColor White
    Write-Host "     aaron setup" -ForegroundColor White
    Write-Host ""
} finally {
    if (Test-Path -LiteralPath $TempRoot) {
        Remove-Item -LiteralPath $TempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
