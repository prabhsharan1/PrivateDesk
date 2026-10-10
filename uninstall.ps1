# ==============================================================================
# PrivateDesk — 1-Line Terminal CLI Uninstaller for Windows (PowerShell)
# ==============================================================================

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  🗑️  Uninstalling PrivateDesk CLI (Windows)" -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Cyan

# Prompt for confirmation
$confirmation = Read-Host "Are you sure you want to completely remove PrivateDesk and its cache? [y/N]"
if ($confirmation -notmatch "^[Yy]$") {
    Write-Host "Uninstallation cancelled." -ForegroundColor Yellow
    exit 0
}

$HomeDir = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::UserProfile)
$PrivateDeskHome = Join-Path $HomeDir ".privatedesk"
$BinDir = Join-Path $PrivateDeskHome "bin"

# 1. Remove from User PATH
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($UserPath -like "*$BinDir*") {
    $NewPath = ($UserPath -split ";" | Where-Object { $_ -ne $BinDir -and $_ -ne "" }) -join ";"
    [Environment]::SetEnvironmentVariable("Path", $NewPath, "User")
    Write-Host "✔ Removed $BinDir from User PATH." -ForegroundColor Green
}

# 2. Remove ~/.privatedesk directory
if (Test-Path $PrivateDeskHome) {
    Write-Host "⚙️ Removing $PrivateDeskHome..." -ForegroundColor Cyan
    Remove-Item -Path $PrivateDeskHome -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "✔ Removed: $PrivateDeskHome" -ForegroundColor Green
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  🎉 PrivateDesk has been completely uninstalled." -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "Note: If you installed Ollama and want to remove it separately, uninstall it via Windows Settings > Installed Apps." -ForegroundColor Gray
