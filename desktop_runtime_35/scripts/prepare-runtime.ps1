param(
    [string]$PythonSource = $env:AARONCORE_BUNDLE_PYTHON_SOURCE,
    [string]$PlaywrightSource = $env:AARONCORE_BUNDLE_PLAYWRIGHT_SOURCE,
    [string]$PythonUserSiteSource = $env:AARONCORE_BUNDLE_PYTHON_USER_SITE_SOURCE
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($PythonSource)) {
    $PythonSource = "C:\Program Files\Python311"
}

if ([string]::IsNullOrWhiteSpace($PlaywrightSource)) {
    $PlaywrightSource = Join-Path $env:LOCALAPPDATA "ms-playwright"
}

if ([string]::IsNullOrWhiteSpace($PythonUserSiteSource)) {
    $PythonUserSiteSource = Join-Path $env:APPDATA "Python\Python311\site-packages"
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$runtimeRoot = Join-Path (Split-Path -Parent $scriptDir) "vendor_runtime"
$pythonDest = Join-Path $runtimeRoot "python"
$playwrightDest = Join-Path $runtimeRoot "ms-playwright"
$pythonSitePackagesDest = Join-Path $pythonDest "Lib\site-packages"

foreach ($source in @($PythonSource, $PlaywrightSource)) {
    if (-not (Test-Path -LiteralPath $source)) {
        throw "Required runtime source not found: $source"
    }
}

New-Item -ItemType Directory -Force -Path $runtimeRoot | Out-Null

function Sync-Directory {
    param(
        [string]$Source,
        [string]$Destination
    )

    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    $null = robocopy $Source $Destination /MIR /R:1 /W:1 /NFL /NDL /NJH /NJS /NP
    if ($LASTEXITCODE -gt 7) {
        throw "robocopy failed for $Source -> $Destination (exit code $LASTEXITCODE)"
    }
}

Write-Host "Syncing bundled Python runtime..."
Sync-Directory -Source $PythonSource -Destination $pythonDest

if (Test-Path -LiteralPath $PythonUserSiteSource) {
    Write-Host "Merging user site-packages into bundled Python..."
    Sync-Directory -Source $PythonUserSiteSource -Destination $pythonSitePackagesDest
}

Write-Host "Syncing bundled Playwright browsers..."
Sync-Directory -Source $PlaywrightSource -Destination $playwrightDest

$pythonUserSiteManifest = $null
if (Test-Path -LiteralPath $PythonUserSiteSource) {
    $pythonUserSiteManifest = $PythonUserSiteSource
}

$manifest = @{
    prepared_at = (Get-Date).ToString("s")
    python_source = $PythonSource
    python_user_site_source = $pythonUserSiteManifest
    playwright_source = $PlaywrightSource
} | ConvertTo-Json -Depth 3

Set-Content -LiteralPath (Join-Path $runtimeRoot "manifest.json") -Value $manifest -Encoding UTF8
Write-Host "Bundled runtime ready at $runtimeRoot"
