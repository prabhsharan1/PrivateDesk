# ==============================================================================
# PrivateDesk — 1-Line Terminal CLI Installer for Windows (PowerShell)
# ==============================================================================

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  🚀 Installing PrivateDesk Terminal AI Assistant (Windows)" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Check & Install Python
$PythonBin = ""
if (Get-Command python -ErrorAction SilentlyContinue) {
    $PythonBin = "python"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $PythonBin = "py"
} else {
    Write-Host "⚠️ Python 3.10+ is required but not detected." -ForegroundColor Yellow
    $installPy = Read-Host "Would you like PrivateDesk to automatically install Python 3 via winget? [Y/n]"
    if ($installPy -match "^[Yy]$" -or $installPy -eq "") {
        if (Get-Command winget -ErrorAction SilentlyContinue) {
            Write-Host "⚙️ Installing Python 3.12 via winget..." -ForegroundColor Cyan
            winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
            # Refresh Path in current session
            $env:Path = [System.Environment]::GetEnvironmentVariable("Path","User") + ";" + [System.Environment]::GetEnvironmentVariable("Path","Machine")
            if (Get-Command python -ErrorAction SilentlyContinue) { $PythonBin = "python" }
            elseif (Get-Command py -ErrorAction SilentlyContinue) { $PythonBin = "py" }
        } else {
            Write-Host "❌ winget is not available. Please install Python from https://python.org" -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "Python installation cancelled. Exiting." -ForegroundColor Red
        exit 1
    }
}

$PyVersion = & $PythonBin --version
Write-Host "✔ Detected Python: $PyVersion" -ForegroundColor Green

# 2. Determine App Directory
$HomeDir = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::UserProfile)
$PrivateDeskHome = Join-Path $HomeDir ".privatedesk"
$AppDir = Join-Path $PrivateDeskHome "app"
$VenvDir = Join-Path $PrivateDeskHome "venv"

# Check if running from local repo clone or piped via web
if (Test-Path "cli.py") {
    $AppDir = (Get-Item .).FullName
    Write-Host "✔ Running from local project: $AppDir" -ForegroundColor Green
} else {
    Write-Host "⚙️ Setting up application directory at: $AppDir" -ForegroundColor Cyan
    New-Item -ItemType Directory -Path $AppDir -Force | Out-Null
    
    if (Get-Command git -ErrorAction SilentlyContinue) {
        git clone --depth 1 https://github.com/prabhsharan1/PrivateDesk.git $AppDir 2>$null
    } else {
        Invoke-WebRequest -Uri "https://raw.githubusercontent.com/prabhsharan1/PrivateDesk/main/cli.py" -OutFile (Join-Path $AppDir "cli.py") -UseBasicParsing
        Invoke-WebRequest -Uri "https://raw.githubusercontent.com/prabhsharan1/PrivateDesk/main/parser.py" -OutFile (Join-Path $AppDir "parser.py") -UseBasicParsing
        Invoke-WebRequest -Uri "https://raw.githubusercontent.com/prabhsharan1/PrivateDesk/main/retriever.py" -OutFile (Join-Path $AppDir "retriever.py") -UseBasicParsing
        Invoke-WebRequest -Uri "https://raw.githubusercontent.com/prabhsharan1/PrivateDesk/main/storage.py" -OutFile (Join-Path $AppDir "storage.py") -UseBasicParsing
        Invoke-WebRequest -Uri "https://raw.githubusercontent.com/prabhsharan1/PrivateDesk/main/llm_engine.py" -OutFile (Join-Path $AppDir "llm_engine.py") -UseBasicParsing
        Invoke-WebRequest -Uri "https://raw.githubusercontent.com/prabhsharan1/PrivateDesk/main/requirements.txt" -OutFile (Join-Path $AppDir "requirements.txt") -UseBasicParsing
    }
}

# 3. Setup Virtual Environment
if (-not (Test-Path $VenvDir)) {
    Write-Host "⚙️ Creating virtual environment at $VenvDir..." -ForegroundColor Cyan
    & $PythonBin -m venv $VenvDir
}

$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$VenvPip = Join-Path $VenvDir "Scripts\pip.exe"

# 4. Install Dependencies
Write-Host "📦 Installing dependencies (pypdf, python-pptx, requests)..." -ForegroundColor Cyan
& $VenvPip install --quiet --upgrade pip
& $VenvPip install --quiet -r (Join-Path $AppDir "requirements.txt")

# 5. Check & Provision Local AI Engine (Ollama + Qwen 2.5)
Write-Host "🧠 Checking local AI engine..." -ForegroundColor Cyan
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host "⚠️ Ollama is required for 100% offline, on-device AI inference." -ForegroundColor Yellow
    $installOllama = Read-Host "Would you like PrivateDesk to install Ollama via winget? [Y/n]"
    if ($installOllama -match "^[Yy]$" -or $installOllama -eq "") {
        if (Get-Command winget -ErrorAction SilentlyContinue) {
            Write-Host "⚙️ Installing Ollama via winget..." -ForegroundColor Cyan
            winget install -e --id Ollama.Ollama --accept-source-agreements --accept-package-agreements
            $env:Path = [System.Environment]::GetEnvironmentVariable("Path","User") + ";" + [System.Environment]::GetEnvironmentVariable("Path","Machine")
        } else {
            Write-Host "ℹ️ Please install Ollama manually from https://ollama.com/download/windows" -ForegroundColor Yellow
        }
    }
}

if (Get-Command ollama -ErrorAction SilentlyContinue) {
    Write-Host "✔ Found Ollama. Ensuring Qwen 2.5 (1.5B) model is ready..." -ForegroundColor Green
    if (-not (Get-Process -Name "ollama" -ErrorAction SilentlyContinue)) {
        Start-Process "ollama" -ArgumentList "serve" -WindowStyle Hidden
        Start-Sleep -Seconds 3
    }
    ollama pull qwen2.5:1.5b
}

# 6. Create Global Executable (privatedesk.cmd)
$BinDir = Join-Path $PrivateDeskHome "bin"
New-Item -ItemType Directory -Path $BinDir -Force | Out-Null

$CmdWrapper = Join-Path $BinDir "privatedesk.cmd"
"@echo off`n`"$VenvPython`" `"$AppDir\cli.py`" %*" | Out-File -FilePath $CmdWrapper -Encoding ascii

Write-Host "✔ Created executable at: $CmdWrapper" -ForegroundColor Green

# 7. Add to User PATH & active PowerShell session
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($UserPath -notlike "*$BinDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$UserPath;$BinDir", "User")
    Write-Host "✔ Added $BinDir to User PATH." -ForegroundColor Green
}
$env:Path = "$env:Path;$BinDir"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  🎉 PrivateDesk Windows Installation Complete!" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "To start using PrivateDesk, open a new PowerShell window and run:"
Write-Host "  privatedesk" -ForegroundColor Green
Write-Host ""
Write-Host "Useful Commands in PowerShell:"
Write-Host "  • privatedesk `"What is our refund policy?`""
Write-Host "  • Get-Clipboard | privatedesk"
Write-Host "==========================================================" -ForegroundColor Cyan
