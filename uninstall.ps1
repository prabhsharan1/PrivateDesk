# ==============================================================================
# PrivateDesk — 1-Line Terminal CLI Uninstaller for Windows (PowerShell)
#   irm https://raw.githubusercontent.com/prabhsharan1/PrivateDesk/main/uninstall.ps1 | iex
# ==============================================================================

function Uninstall-PrivateDesk {
    $ErrorActionPreference = "Continue"

    Write-Host "==========================================================" -ForegroundColor Cyan
    Write-Host "  Uninstalling PrivateDesk CLI (Windows)" -ForegroundColor Yellow
    Write-Host "==========================================================" -ForegroundColor Cyan

    $confirmation = if ($env:PRIVATEDESK_YES -eq "1") { "y" } else { Read-Host "Completely remove PrivateDesk, its virtual environment and cached documents? [y/N]" }
    if ($confirmation -notmatch "^[Yy]") {
        Write-Host "Uninstallation cancelled." -ForegroundColor Yellow
        return
    }

    $HomeDir = $env:USERPROFILE
    if (-not $HomeDir) { $HomeDir = [Environment]::GetFolderPath("UserProfile") }
    $HomeDir = $HomeDir.TrimEnd('\', '/')
    $PrivateDeskHome = "$HomeDir\.privatedesk"
    $BinDir = "$PrivateDeskHome\bin"

    # 1. Remove from User PATH (exact-match entries only)
    $UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($UserPath) {
        $entries = $UserPath -split ";" | Where-Object { $_ }
        if ($entries -contains $BinDir) {
            [Environment]::SetEnvironmentVariable("Path", (($entries | Where-Object { $_ -ne $BinDir }) -join ";"), "User")
            Write-Host "Removed $BinDir from User PATH." -ForegroundColor Green
        }
    }
    $env:Path = ($env:Path -split ";" | Where-Object { $_ -and $_ -ne $BinDir }) -join ";"

    # 2. Remove ~/.privatedesk (app, venv, bin, cached documents)
    if (Test-Path $PrivateDeskHome) {
        Remove-Item -Path $PrivateDeskHome -Recurse -Force -ErrorAction SilentlyContinue
        if (Test-Path $PrivateDeskHome) {
            Write-Host "Some files are still in use. Close any open 'privatedesk' windows and run this again." -ForegroundColor Yellow
        } else {
            Write-Host "Removed: $PrivateDeskHome" -ForegroundColor Green
        }
    }

    # 3. Remove leftovers from earlier broken installer runs (missing path separator)
    $Leftover = "$HomeDir.privatedesk"
    if (Test-Path $Leftover) {
        Remove-Item -Path $Leftover -Recurse -Force -ErrorAction SilentlyContinue
    }

    Write-Host "==========================================================" -ForegroundColor Cyan
    Write-Host "  PrivateDesk has been uninstalled." -ForegroundColor Green
    Write-Host "==========================================================" -ForegroundColor Cyan
    Write-Host "Note: Ollama and Python are left in place. Remove them via Settings > Installed Apps if you want." -ForegroundColor Gray
}

Uninstall-PrivateDesk
