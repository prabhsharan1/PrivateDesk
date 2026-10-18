# ==============================================================================
# PrivateDesk -- 1-Line Terminal CLI Uninstaller for Windows (PowerShell 5.1+ / 7+)
#   irm https://raw.githubusercontent.com/prabhsharan1/PrivateDesk/main/uninstall.ps1 | iex
# ==============================================================================

function Uninstall-PrivateDesk {
    $ErrorActionPreference = "Continue"

    Write-Host "==========================================================" -ForegroundColor Cyan
    Write-Host "  PrivateDesk Uninstallation Manager (Windows)" -ForegroundColor Yellow
    Write-Host "==========================================================" -ForegroundColor Cyan

    $HomeDir = $env:USERPROFILE
    if (-not $HomeDir) { $HomeDir = [Environment]::GetFolderPath("UserProfile") }
    $HomeDir = $HomeDir.TrimEnd('\', '/')
    $PrivateDeskHome = "$HomeDir\.privatedesk"
    $BinDir = "$PrivateDeskHome\bin"
    $VenvDir = "$PrivateDeskHome\venv"
    $PortablePy = "$PrivateDeskHome\python"
    $StoreJson = "$PrivateDeskHome\store.json"
    $AppDir = "$PrivateDeskHome\app"

    # Helper function to locate Ollama executable
    function Find-Ollama {
        $cmd = Get-Command ollama -ErrorAction SilentlyContinue
        if ($cmd) { return $cmd.Source }
        $defaultPath = "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"
        if (Test-Path $defaultPath) { return $defaultPath }
        return $null
    }

    $RemoveApp = $false
    $RemoveVenv = $false
    $RemoveCache = $false
    $RemoveModel = $false
    $RemoveOllama = $false
    $RemovePortablePy = $false

    if ($env:PRIVATEDESK_YES -eq "1") {
        # Unattended / CI mode: clean removal of PrivateDesk app, venv, cache & portable python
        $RemoveApp = $true
        $RemoveVenv = $true
        $RemoveCache = $true
        $RemovePortablePy = $true
    } else {
        Write-Host ""
        Write-Host "Please select an uninstallation option:"
        Write-Host ""
        Write-Host "  [1] Complete / Everything" -ForegroundColor White
        Write-Host "      * Remove PrivateDesk application & launcher" -ForegroundColor Gray
        Write-Host "      * Remove Python virtual environment & dependencies" -ForegroundColor Gray
        Write-Host "      * Remove Knowledge Vault & document cache" -ForegroundColor Gray
        Write-Host "      * Remove Qwen 2.5 AI model from Ollama (frees ~1GB)" -ForegroundColor Gray
        Write-Host "      * Uninstall Ollama application" -ForegroundColor Gray
        if (Test-Path $PortablePy) {
            Write-Host "      * Remove PrivateDesk portable Python" -ForegroundColor Gray
        }
        Write-Host ""
        Write-Host "  [2] PrivateDesk Only (Keep Ollama & AI Models) [Default]" -ForegroundColor White
        Write-Host "      * Remove PrivateDesk app, launcher, venv, and cache" -ForegroundColor Gray
        Write-Host "      * Preserves Ollama and AI models for other applications" -ForegroundColor Gray
        Write-Host ""
        Write-Host "  [3] Custom / Selective Uninstall" -ForegroundColor White
        Write-Host "      * Choose individually what to delete or keep" -ForegroundColor Gray
        Write-Host ""
        Write-Host "  [4] Cancel" -ForegroundColor White
        Write-Host ""

        $choice = Read-Host "Enter choice [1-4] (default: 2)"
        if ($choice) { $choice = $choice.Trim() } else { $choice = "2" }

        switch ($choice) {
            "1" {
                $confirm = Read-Host "This will remove PrivateDesk, dependencies, Qwen model, and Ollama. Proceed? [y/N]"
                if ($confirm -notmatch "^[Yy]") {
                    Write-Host "Uninstallation cancelled." -ForegroundColor Yellow
                    return
                }
                $RemoveApp = $true
                $RemoveVenv = $true
                $RemoveCache = $true
                $RemoveModel = $true
                $RemoveOllama = $true
                $RemovePortablePy = $true
            }
            "2" {
                $confirm = Read-Host "Remove PrivateDesk, its virtual environment and cached documents? [y/N]"
                if ($confirm -notmatch "^[Yy]") {
                    Write-Host "Uninstallation cancelled." -ForegroundColor Yellow
                    return
                }
                $RemoveApp = $true
                $RemoveVenv = $true
                $RemoveCache = $true
                $RemovePortablePy = $true
            }
            "3" {
                Write-Host ""
                Write-Host "Select components to remove:" -ForegroundColor Cyan
                $ansApp = Read-Host "Remove PrivateDesk application and CLI command? [Y/n]"
                $RemoveApp = ($ansApp -notmatch "^[Nn]")

                $ansVenv = Read-Host "Remove Python virtual environment and dependencies ($VenvDir)? [Y/n]"
                $RemoveVenv = ($ansVenv -notmatch "^[Nn]")

                $ansCache = Read-Host "Remove Knowledge Vault and document cache ($StoreJson)? [Y/n]"
                $RemoveCache = ($ansCache -notmatch "^[Nn]")

                if (Find-Ollama) {
                    $ansModel = Read-Host "Remove Qwen 2.5 AI model from Ollama (frees ~1GB)? [y/N]"
                    $RemoveModel = ($ansModel -match "^[Yy]")

                    $ansOllama = Read-Host "Uninstall Ollama application entirely? [y/N]"
                    $RemoveOllama = ($ansOllama -match "^[Yy]")
                }

                if (Test-Path $PortablePy) {
                    $ansPy = Read-Host "Remove PrivateDesk portable Python ($PortablePy)? [Y/n]"
                    $RemovePortablePy = ($ansPy -notmatch "^[Nn]")
                }
            }
            default {
                Write-Host "Uninstallation cancelled." -ForegroundColor Yellow
                return
            }
        }
    }

    $OllamaExe = Find-Ollama

    # 1. Remove Qwen AI Model from Ollama
    if ($RemoveModel -and $OllamaExe) {
        Write-Host "Removing Qwen 2.5 AI model from Ollama..." -ForegroundColor Cyan
        & $OllamaExe rm qwen2.5:1.5b 2>$null
        & $OllamaExe rm qwen2.5:1.5b-instruct 2>$null
        Write-Host "[OK] Removed Qwen 2.5 AI model." -ForegroundColor Green
    }

    # 2. Uninstall Ollama Application
    if ($RemoveOllama) {
        Write-Host "Uninstalling Ollama application..." -ForegroundColor Cyan
        Stop-Process -Name "ollama" -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 500

        $uninstaller = "$env:LOCALAPPDATA\Programs\Ollama\Uninstall.exe"
        if (Test-Path $uninstaller) {
            Start-Process -FilePath $uninstaller -ArgumentList "/S" -Wait -ErrorAction SilentlyContinue
        } elseif (Get-Command winget -ErrorAction SilentlyContinue) {
            winget uninstall -e --id Ollama.Ollama --silent 2>$null
        }

        if (Test-Path "$env:LOCALAPPDATA\Programs\Ollama") {
            Remove-Item -Path "$env:LOCALAPPDATA\Programs\Ollama" -Recurse -Force -ErrorAction SilentlyContinue
        }
        if (Test-Path "$env:USERPROFILE\.ollama") {
            Remove-Item -Path "$env:USERPROFILE\.ollama" -Recurse -Force -ErrorAction SilentlyContinue
        }
        Write-Host "[OK] Removed Ollama application and models." -ForegroundColor Green
    }

    # 3. Remove executable & User PATH
    if ($RemoveApp) {
        $UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
        if ($UserPath) {
            $entries = $UserPath -split ";" | Where-Object { $_ }
            if ($entries -contains $BinDir) {
                [Environment]::SetEnvironmentVariable("Path", (($entries | Where-Object { $_ -ne $BinDir }) -join ";"), "User")
                Write-Host "Removed $BinDir from User PATH." -ForegroundColor Green
            }
        }
        $env:Path = ($env:Path -split ";" | Where-Object { $_ -and $_ -ne $BinDir }) -join ";"
        if (Test-Path $BinDir) {
            Remove-Item -Path $BinDir -Recurse -Force -ErrorAction SilentlyContinue
            Write-Host "[OK] Removed launcher executable: $BinDir" -ForegroundColor Green
        }
        if (Test-Path $AppDir) {
            Remove-Item -Path $AppDir -Recurse -Force -ErrorAction SilentlyContinue
            Write-Host "[OK] Removed application files: $AppDir" -ForegroundColor Green
        }
    }

    # 4. Remove Python virtual environment and dependencies
    if ($RemoveVenv -and (Test-Path $VenvDir)) {
        Remove-Item -Path $VenvDir -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "[OK] Removed Python virtual environment and dependencies: $VenvDir" -ForegroundColor Green
    }

    # 5. Remove PrivateDesk portable Python
    if ($RemovePortablePy -and (Test-Path $PortablePy)) {
        Remove-Item -Path $PortablePy -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "[OK] Removed PrivateDesk portable Python: $PortablePy" -ForegroundColor Green
    }

    # 6. Remove Knowledge Vault and document cache
    if ($RemoveCache) {
        if (Test-Path $StoreJson) {
            Remove-Item -Path $StoreJson -Force -ErrorAction SilentlyContinue
            Write-Host "[OK] Removed Knowledge Vault cache: $StoreJson" -ForegroundColor Green
        }
        if (Test-Path "$PrivateDeskHome\data") {
            Remove-Item -Path "$PrivateDeskHome\data" -Recurse -Force -ErrorAction SilentlyContinue
        }
    }

    # 7. Clean up ~/.privatedesk directory
    if (Test-Path $PrivateDeskHome) {
        if ($RemoveApp -and $RemoveVenv -and $RemoveCache -and ($RemovePortablePy -or (-not (Test-Path $PortablePy)))) {
            Remove-Item -Path $PrivateDeskHome -Recurse -Force -ErrorAction SilentlyContinue
            if (Test-Path $PrivateDeskHome) {
                Write-Host "Some files in $PrivateDeskHome are still in use. Close open terminals and re-run." -ForegroundColor Yellow
            } else {
                Write-Host "[OK] Removed: $PrivateDeskHome" -ForegroundColor Green
            }
        } else {
            $remaining = Get-ChildItem -Path $PrivateDeskHome -Force -ErrorAction SilentlyContinue
            if (-not $remaining) {
                Remove-Item -Path $PrivateDeskHome -Recurse -Force -ErrorAction SilentlyContinue
                Write-Host "[OK] Removed empty directory: $PrivateDeskHome" -ForegroundColor Green
            }
        }
    }

    # 8. Remove leftovers from earlier broken installer runs (missing path separator)
    $Leftover = "$HomeDir.privatedesk"
    if (Test-Path $Leftover) {
        Remove-Item -Path $Leftover -Recurse -Force -ErrorAction SilentlyContinue
    }

    Write-Host "==========================================================" -ForegroundColor Cyan
    Write-Host "  Uninstallation complete." -ForegroundColor Green
    Write-Host "==========================================================" -ForegroundColor Cyan
    if (-not $RemoveOllama -and -not $RemoveModel) {
        Write-Host "Note: Ollama and your AI models were preserved for other applications." -ForegroundColor Gray
    }
}

Uninstall-PrivateDesk
