# ==============================================================================
# PrivateDesk — 1-Line Terminal CLI Installer for Windows (PowerShell 5.1+ / 7+)
#   irm https://raw.githubusercontent.com/prabhsharan1/PrivateDesk/main/install.ps1 | iex
# ==============================================================================
# Everything lives inside a function so that `return` is used instead of `exit`
# (calling `exit` under `| iex` would close the user's PowerShell window).

function Install-PrivateDesk {
    # Native commands write warnings to stderr; "Stop" would turn those into fatal errors on PS 5.1.
    $ErrorActionPreference = "Continue"
    try { [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12 } catch {}

    $RepoRaw = "https://raw.githubusercontent.com/prabhsharan1/PrivateDesk/main"
    $RepoGit = "https://github.com/prabhsharan1/PrivateDesk.git"
    $AppFiles = @("cli.py", "parser.py", "retriever.py", "storage.py", "llm_engine.py", "requirements.txt")

    function Say($msg, $color = "Cyan") { Write-Host $msg -ForegroundColor $color }
    function Refresh-SessionPath {
        $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
        $user = [Environment]::GetEnvironmentVariable("Path", "User")
        $env:Path = (@($user, $machine) | Where-Object { $_ }) -join ";"
    }
    function Ask-YesNo($question) {
        $reply = Read-Host "$question [Y/n]"
        return ($reply -eq "" -or $reply -match "^[Yy]")
    }

    Say "==========================================================" "Cyan"
    Say "  Installing PrivateDesk Terminal AI Assistant (Windows)" "Green"
    Say "==========================================================" "Cyan"

    # ------------------------------------------------------------------ 1. Python
    # `Get-Command python` can succeed on the Microsoft Store *stub* (WindowsApps\python.exe),
    # which exists but cannot run or create a venv. So every candidate is actually executed.
    function Test-PythonCandidate($exe, $pyArgs) {
        try {
            $out = & $exe @pyArgs -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>&1 | Select-Object -First 1
            if ($LASTEXITCODE -ne 0) { return $null }
            if ("$out" -match '^(\d+)\.(\d+)$' -and [int]$Matches[1] -eq 3 -and [int]$Matches[2] -ge 9) {
                return @{ Exe = $exe; Args = $pyArgs; Version = "$out" }
            }
        } catch {}
        return $null
    }

    function Find-Python {
        $candidates = @(
            @{ Exe = "py";      Args = @("-3") },
            @{ Exe = "python";  Args = @() },
            @{ Exe = "python3"; Args = @() }
        )
        foreach ($c in $candidates) {
            if (Get-Command $c.Exe -ErrorAction SilentlyContinue) {
                $found = Test-PythonCandidate $c.Exe $c.Args
                if ($found) { return $found }
            }
        }
        $globs = @(
            "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe",
            "$env:ProgramFiles\Python3*\python.exe",
            "${env:ProgramFiles(x86)}\Python3*\python.exe"
        )
        foreach ($g in $globs) {
            foreach ($f in (Get-ChildItem -Path $g -ErrorAction SilentlyContinue | Sort-Object FullName -Descending)) {
                $found = Test-PythonCandidate $f.FullName @()
                if ($found) { return $found }
            }
        }
        return $null
    }

    $Py = Find-Python
    if (-not $Py) {
        Say "Python 3.9+ is required but no working Python was found." "Yellow"
        Say "(Windows may list a Microsoft Store 'python' shortcut, but it is not a real install.)" "DarkGray"
        if (-not (Ask-YesNo "Install Python 3.12 automatically?")) {
            Say "Python is required. Install it from https://www.python.org/downloads/ and re-run this command." "Red"
            return
        }

        # Attempt 1: winget, pinned to the 'winget' source. The default search also queries the
        # 'msstore' source, which fails with 0x8a15000f on PCs that never accepted its agreement.
        if (Get-Command winget -ErrorAction SilentlyContinue) {
            Say "Installing Python 3.12 via winget (this can take a minute)..." "Cyan"
            winget install -e --id Python.Python.3.12 --source winget --scope user --silent --accept-source-agreements --accept-package-agreements
            if ($LASTEXITCODE -ne 0) {
                Say "winget could not install Python (exit code $LASTEXITCODE). Trying the official python.org installer instead..." "Yellow"
            }
            Refresh-SessionPath
            $Py = Find-Python
        }

        # Attempt 2: official python.org installer, per-user, silent, no admin rights needed.
        if (-not $Py) {
            $arch = if ($env:PROCESSOR_ARCHITECTURE -eq "ARM64") { "arm64" } else { "amd64" }
            $pyUrl = "https://www.python.org/ftp/python/3.12.8/python-3.12.8-$arch.exe"
            $pyExe = "$env:TEMP\python-3.12.8-$arch.exe"
            try {
                Say "Downloading Python 3.12 from python.org ($arch)..." "Cyan"
                Invoke-WebRequest -Uri $pyUrl -OutFile $pyExe -UseBasicParsing
                Say "Installing Python (per-user, silent)..." "Cyan"
                $p = Start-Process -FilePath $pyExe -ArgumentList "/quiet", "InstallAllUsers=0", "PrependPath=1", "Include_launcher=1", "Include_test=0", "Include_doc=0" -Wait -PassThru
                if ($p.ExitCode -ne 0) { Say "Python installer exited with code $($p.ExitCode)." "Yellow" }
            } catch {
                Say "Could not download/run the Python installer: $($_.Exception.Message)" "Red"
            } finally {
                Remove-Item -Path $pyExe -Force -ErrorAction SilentlyContinue
            }
            Refresh-SessionPath
            $Py = Find-Python
        }

        if (-not $Py) {
            Say "Python could not be installed automatically." "Red"
            Say "  1) Download it from https://www.python.org/downloads/ (tick 'Add python.exe to PATH')" "Yellow"
            Say "  2) Open a NEW PowerShell window and re-run the install command." "Yellow"
            return
        }
        Say "Python installed successfully." "Green"
    }
    Say "Detected Python $($Py.Version) ($($Py.Exe))" "Green"

    # ------------------------------------------------------------------ 2. Paths
    $HomeDir = $env:USERPROFILE
    if (-not $HomeDir) { $HomeDir = [Environment]::GetFolderPath("UserProfile") }
    $HomeDir = $HomeDir.TrimEnd('\', '/')
    $PrivateDeskHome = "$HomeDir\.privatedesk"
    $AppDir = "$PrivateDeskHome\app"
    $VenvDir = "$PrivateDeskHome\venv"
    $BinDir = "$PrivateDeskHome\bin"
    $VenvPython = "$VenvDir\Scripts\python.exe"
    New-Item -ItemType Directory -Path $PrivateDeskHome -Force | Out-Null

    # ------------------------------------------------------------------ 3. App files
    if (Test-Path ".\cli.py") {
        $AppDir = (Get-Item .).FullName
        Say "Running from local project: $AppDir" "Green"
    } else {
        Say "Setting up application directory at: $AppDir" "Cyan"
        $ok = $false
        if (Test-Path "$AppDir\.git") {
            if (Get-Command git -ErrorAction SilentlyContinue) {
                git -C $AppDir pull --ff-only 2>&1 | Out-Null
                $ok = ($LASTEXITCODE -eq 0)
            }
        } elseif (Get-Command git -ErrorAction SilentlyContinue) {
            if (Test-Path $AppDir) { Remove-Item -Path $AppDir -Recurse -Force -ErrorAction SilentlyContinue }
            git clone --depth 1 $RepoGit $AppDir 2>&1 | Out-Null
            $ok = ($LASTEXITCODE -eq 0)
        }
        if (-not $ok -or -not (Test-Path "$AppDir\cli.py")) {
            New-Item -ItemType Directory -Path $AppDir -Force | Out-Null
            try {
                foreach ($f in $AppFiles) {
                    Invoke-WebRequest -Uri "$RepoRaw/$f" -OutFile "$AppDir\$f" -UseBasicParsing
                }
            } catch {
                Say "Could not download PrivateDesk files. Check your internet connection and try again. ($($_.Exception.Message))" "Red"
                return
            }
        }
        if (-not (Test-Path "$AppDir\cli.py")) {
            Say "Download finished but cli.py is missing. Aborting." "Red"
            return
        }
    }

    # ------------------------------------------------------------------ 4. Virtual environment
    if (-not (Test-Path $VenvPython)) {
        Say "Creating virtual environment at $VenvDir ..." "Cyan"
        if (Test-Path $VenvDir) { Remove-Item -Path $VenvDir -Recurse -Force -ErrorAction SilentlyContinue }
        & $Py.Exe @($Py.Args) -m venv $VenvDir 2>&1 | Out-Null
        if (-not (Test-Path $VenvPython)) {
            # Some installs lack ensurepip; retry without pip and bootstrap it ourselves.
            & $Py.Exe @($Py.Args) -m venv --without-pip $VenvDir 2>&1 | Out-Null
        }
        if (-not (Test-Path $VenvPython)) {
            Say "Failed to create the Python virtual environment." "Red"
            Say "  Python used : $($Py.Exe) $($Py.Args -join ' ') (v$($Py.Version))" "Yellow"
            Say "  Expected    : $VenvPython" "Yellow"
            Say "  Try re-installing Python from https://www.python.org/downloads/ (include 'pip' and 'venv'), then re-run." "Yellow"
            return
        }
    }

    # ------------------------------------------------------------------ 5. Dependencies
    Say "Installing dependencies (pypdf, python-pptx, requests)..." "Cyan"
    & $VenvPython -m pip --version 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        & $VenvPython -m ensurepip --default-pip 2>&1 | Out-Null
    }
    & $VenvPython -m pip install --quiet --disable-pip-version-check --upgrade pip 2>&1 | Out-Null
    & $VenvPython -m pip install --quiet --disable-pip-version-check -r "$AppDir\requirements.txt"
    if ($LASTEXITCODE -ne 0) {
        Say "Dependency installation failed. Check your internet connection / proxy and re-run." "Red"
        return
    }

    # ------------------------------------------------------------------ 6. Ollama + model
    Say "Checking local AI engine..." "Cyan"
    function Find-Ollama {
        $cmd = Get-Command ollama -ErrorAction SilentlyContinue
        if ($cmd) { return $cmd.Source }
        $p = "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"
        if (Test-Path $p) { return $p }
        return $null
    }
    $Ollama = Find-Ollama
    if (-not $Ollama) {
        Say "Ollama is required for 100% offline, on-device AI." "Yellow"
        if (Ask-YesNo "Install Ollama automatically?") {
            $installed = $false
            if (Get-Command winget -ErrorAction SilentlyContinue) {
                winget install -e --id Ollama.Ollama --source winget --silent --accept-source-agreements --accept-package-agreements
                $installed = ($LASTEXITCODE -eq 0)
                if (-not $installed) { Say "winget could not install Ollama; trying the official installer instead..." "Yellow" }
            }
            if (-not $installed) {
                $setup = "$env:TEMP\OllamaSetup.exe"
                try {
                    Say "Downloading Ollama installer..." "Cyan"
                    Invoke-WebRequest -Uri "https://ollama.com/download/OllamaSetup.exe" -OutFile $setup -UseBasicParsing
                    Start-Process -FilePath $setup -ArgumentList "/SILENT" -Wait
                } catch {
                    Say "Automatic Ollama install failed. Get it from https://ollama.com/download/windows" "Yellow"
                } finally {
                    Remove-Item -Path $setup -Force -ErrorAction SilentlyContinue
                }
            }
            Refresh-SessionPath
            $Ollama = Find-Ollama
        } else {
            Say "Skipping Ollama. PrivateDesk will offer to install it the first time you ask a question." "DarkGray"
        }
    }
    if ($Ollama) {
        Say "Found Ollama. Making sure the Qwen 2.5 (1.5B) model is ready..." "Green"
        $online = $false
        try { Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 2 | Out-Null; $online = $true } catch {}
        if (-not $online) {
            Start-Process -FilePath $Ollama -ArgumentList "serve" -WindowStyle Hidden
            for ($i = 0; $i -lt 15 -and -not $online; $i++) {
                Start-Sleep -Seconds 1
                try { Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 2 | Out-Null; $online = $true } catch {}
            }
        }
        & $Ollama pull qwen2.5:1.5b
        if ($LASTEXITCODE -ne 0) {
            Say "Model download did not finish; PrivateDesk will retry automatically on first use." "Yellow"
        }
    }

    # ------------------------------------------------------------------ 7. Launcher + PATH
    New-Item -ItemType Directory -Path $BinDir -Force | Out-Null
    $CmdWrapper = "$BinDir\privatedesk.cmd"
    $wrapperText = "@echo off`r`n`"$VenvPython`" `"$AppDir\cli.py`" %*`r`n"
    [System.IO.File]::WriteAllText($CmdWrapper, $wrapperText, (New-Object System.Text.UTF8Encoding($false)))
    Say "Created executable: $CmdWrapper" "Green"

    $UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $entries = @()
    if ($UserPath) { $entries = $UserPath -split ";" | Where-Object { $_ } }
    if ($entries -notcontains $BinDir) {
        [Environment]::SetEnvironmentVariable("Path", (($entries + $BinDir) -join ";"), "User")
        Say "Added $BinDir to your User PATH." "Green"
    }
    if (($env:Path -split ";") -notcontains $BinDir) { $env:Path = "$env:Path;$BinDir" }

    Say "==========================================================" "Cyan"
    Say "  PrivateDesk Windows Installation Complete!" "Green"
    Say "==========================================================" "Cyan"
    Write-Host ""
    Write-Host "Start it right now in this window:"
    Say "  privatedesk" "Green"
    Write-Host ""
    Write-Host "Useful commands:"
    Write-Host "  privatedesk `"What is our refund policy?`""
    Write-Host "  Get-Clipboard | privatedesk"
    Write-Host "  privatedesk --uninstall"
    Say "==========================================================" "Cyan"
}

Install-PrivateDesk
