# StatVerdict ship script
# 1) Bumps addon version
# 2) Builds Desktop\StatVerdict-x.y.z.zip for Curse

[CmdletBinding()]
param(
    [switch]$SkipBump,
    [switch]$SkipZip
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot "StatVerdict.toc"))) {
    throw "Cannot find StatVerdict.toc under $ProjectRoot"
}

$DesktopDir = [Environment]::GetFolderPath("Desktop")
$TocPath = Join-Path $ProjectRoot "StatVerdict.toc"
$LuaPath = Join-Path $ProjectRoot "StatVerdict.lua"

Write-Host "Project: $ProjectRoot"

function Get-TocValue([string]$path, [string]$key) {
    $line = Get-Content -LiteralPath $path | Where-Object { $_ -match ("^##\s*" + [regex]::Escape($key) + "\s*:") } | Select-Object -First 1
    if (-not $line) { return $null }
    return ($line -split ":", 2)[1].Trim()
}

function Set-TocValue([string]$path, [string]$key, [string]$value) {
    $lines = Get-Content -LiteralPath $path
    $found = $false
    $out = foreach ($line in $lines) {
        if ($line -match ("^##\s*" + [regex]::Escape($key) + "\s*:")) {
            $found = $true
            "## ${key}: $value"
        } else {
            $line
        }
    }
    if (-not $found) {
        throw "TOC key not found: $key"
    }
    Set-Content -LiteralPath $path -Value $out -Encoding UTF8
}

$version = Get-TocValue $TocPath "Version"
if (-not $version) { $version = "1.0.0" }

# Ensure Interface is current for live.
Set-TocValue $TocPath "Interface" "120100"

if (-not $SkipBump) {
    if ($version -match "^(\d+)\.(\d+)\.(\d+)$") {
        $major = [int]$Matches[1]
        $minor = [int]$Matches[2]
        $patch = [int]$Matches[3] + 1
        $newVersion = "$major.$minor.$patch"
    } else {
        $newVersion = "$version.1"
    }
    Set-TocValue $TocPath "Version" $newVersion
    if (Test-Path -LiteralPath $LuaPath) {
        $lua = Get-Content -LiteralPath $LuaPath -Raw
        $lua2 = [regex]::Replace($lua, 'ns\.VERSION\s*=\s*"[^"]*"', "ns.VERSION = `"$newVersion`"")
        Set-Content -LiteralPath $LuaPath -Value $lua2 -Encoding UTF8 -NoNewline
    }
    $version = $newVersion
    Write-Host "Version bumped to $version"
} else {
    Write-Host "Version left at $version"
}

if ($SkipZip) {
    Write-Host "SkipZip set; no archive created."
    exit 0
}

New-Item -ItemType Directory -Force -Path $DesktopDir | Out-Null
$staging = Join-Path $env:TEMP ("StatVerdict-ship-" + [guid]::NewGuid().ToString("N"))
$stageAddon = Join-Path $staging "StatVerdict"
New-Item -ItemType Directory -Force -Path $stageAddon | Out-Null

$include = @(
    "StatVerdict.toc",
    "StatVerdict.lua",
    "Bindings.xml",
    "STORE.md",
    "Core",
    "UI",
    "Data",
    "Media",
    "Textures"
)

foreach ($name in $include) {
    $src = Join-Path $ProjectRoot $name
    if (Test-Path -LiteralPath $src) {
        Copy-Item -LiteralPath $src -Destination (Join-Path $stageAddon $name) -Recurse -Force
    }
}

# Never ship bridge/dev leftovers if present.
$ban = @(
    (Join-Path $stageAddon "Tools"),
    (Join-Path $stageAddon "UI\SV_AdvancedDevelopmentMode.lua"),
    (Join-Path $stageAddon "UI\SV_DevLayoutNudge.lua"),
    (Join-Path $stageAddon "StatVerdict.toc.public"),
    (Join-Path $stageAddon "_recovery_StatVerdict_SV_2026-07-25.lua.bak")
)
foreach ($path in $ban) {
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Recurse -Force
    }
}

# Public TOC must not reference Removed files.
$tocLines = Get-Content -LiteralPath (Join-Path $stageAddon "StatVerdict.toc") | Where-Object {
    $_ -notmatch "AdvancedDevelopmentMode" -and
    $_ -notmatch "DevLayoutNudge" -and
    $_ -notmatch "Tools/" -and
    $_ -notmatch "StatVerdictBISResolverDB"
}
# Ensure SavedVariables is public-only.
$tocLines = foreach ($line in $tocLines) {
    if ($line -match "^##\s*SavedVariables\s*:") {
        "## SavedVariables: StatVerdictDB"
    } else {
        $line
    }
}
Set-Content -LiteralPath (Join-Path $stageAddon "StatVerdict.toc") -Value $tocLines -Encoding UTF8

$zipPath = Join-Path $DesktopDir "StatVerdict-$version.zip"
if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}

Compress-Archive -Path (Join-Path $staging "StatVerdict") -DestinationPath $zipPath -Force
Remove-Item -LiteralPath $staging -Recurse -Force

Write-Host ""
Write-Host "DONE"
Write-Host "Zip ready on Desktop: $zipPath"
Write-Host "Upload that zip to CurseForge."
