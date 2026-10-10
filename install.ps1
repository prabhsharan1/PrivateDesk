# ==============================================================================
# PrivateDesk — 1-Line Terminal CLI Installer for Windows (PowerShell)
# ==============================================================================

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  🚀 Installing PrivateDesk Terminal AI Assistant (Windows)" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Check Python
$PythonBin = ""
if (Get-Command python -ErrorAction SilentlyContinue) {
    $PythonBin = "python"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $PythonBin = "py"
} else {
    Write-Host "❌ Error: Python 3 is required. Please install Python 3.10+ from python.org or Microsoft Store." -ForegroundColor Red
    exit 1
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

# 5. Check Ollama
Write-Host "🧠 Checking local AI engine..." -ForegroundColor Cyan
if (Get-Command ollama -ErrorAction SilentlyContinue) {
    Write-Host "✔ Found Ollama. Ensuring Qwen 2.5 (1.5B) model is ready..." -ForegroundColor Green
    ollama pull qwen2.5:1.5b
} else {
    Write-Host "ℹ️ Ollama not found in PATH." -ForegroundColor Yellow
    Write-Host "   To enable offline AI on Windows, download Ollama from: https://ollama.com/download/windows" -ForegroundColor Yellow
}

# 6. Create Global Executable (privatedesk.cmd)
$BinDir = Join-Path $PrivateDeskHome "bin"
New-Item -ItemType Directory -Path $BinDir -Force | Out-Null

$CmdWrapper = Join-Path $BinDir "privatedesk.cmd"
"@echo off`n`"$VenvPython`" `"$AppDir\cli.py`" %*" | Out-File -FilePath $CmdWrapper -Encoding ascii

Write-Host "✔ Created executable at: $CmdWrapper" -ForegroundColor Green

# 7. Add to User PATH if not present
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($UserPath -notlike "*$BinDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$UserPath;$BinDir", "User")
    Write-Host "✔ Added $BinDir to User PATH." -ForegroundColor Green
}

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
