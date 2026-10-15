#!/usr/bin/env bash
# ==============================================================================
# PrivateDesk — 1-Line Terminal CLI Installer for macOS / Linux
#   curl -fsSL https://raw.githubusercontent.com/prabhsharan1/PrivateDesk/main/install.sh | bash
# ==============================================================================

set -u   # (no `set -e`: every step is checked explicitly so failures give clear messages)

BOLD="\033[1m"; DIM="\033[2m"; RED="\033[31m"; GREEN="\033[32m"
CYAN="\033[36m"; YELLOW="\033[33m"; RESET="\033[0m"

REPO_GIT="https://github.com/prabhsharan1/PrivateDesk.git"
REPO_RAW="https://raw.githubusercontent.com/prabhsharan1/PrivateDesk/main"
APP_FILES="cli.py parser.py retriever.py storage.py llm_engine.py requirements.txt"

say()  { echo -e "$1"; }
die()  { echo -e "${RED}❌ $1${RESET}"; exit 1; }

say "${CYAN}==========================================================${RESET}"
say "${BOLD}  🚀 Installing PrivateDesk Terminal AI Assistant${RESET}"
say "${CYAN}==========================================================${RESET}"

# Prompt that also works when the script itself is piped through `curl | bash`
ask_permission() {
    # Unattended mode (CI / scripted installs): PRIVATEDESK_YES=1 answers "yes" to every prompt.
    [ "${PRIVATEDESK_YES:-}" = "1" ] && return 0
    local prompt_msg="$1" default_ans="${2:-y}" reply=""
    if [ -t 0 ]; then
        read -r -p "$prompt_msg " reply
    elif [ -r /dev/tty ]; then
        read -r -p "$prompt_msg " reply < /dev/tty || reply="$default_ans"
    else
        reply="$default_ans"
    fi
    reply="${reply:-$default_ans}"
    [[ "$reply" =~ ^[Yy] ]]
}

# Homebrew lives outside the default PATH on Apple Silicon (/opt/homebrew) in non-login shells.
load_brew_env() {
    for b in /opt/homebrew/bin/brew /usr/local/bin/brew /home/linuxbrew/.linuxbrew/bin/brew; do
        if [ -x "$b" ]; then eval "$("$b" shellenv)"; return 0; fi
    done
    return 1
}
load_brew_env || true

# ------------------------------------------------------------------ 1. Python (3.9+)
# `command -v python3` is NOT enough: on a fresh Mac, /usr/bin/python3 is an Xcode stub that
# pops up an installer dialog and fails. So every candidate is actually executed and version-checked.
find_python() {
    local c
    for c in python3.13 python3.12 python3.11 python3.10 python3 python; do
        if command -v "$c" >/dev/null 2>&1; then
            if "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1; then
                echo "$c"; return 0
            fi
        fi
    done
    return 1
}

PYTHON_BIN="$(find_python || true)"

if [ -z "$PYTHON_BIN" ]; then
    say "${YELLOW}⚠️ A working Python 3.9+ was not found.${RESET}"
    if ask_permission "Install Python 3 automatically now? [Y/n]"; then
        if command -v brew >/dev/null 2>&1; then
            say "${CYAN}🍺 Installing Python via Homebrew...${RESET}"
            brew install python || die "Homebrew could not install Python."
        elif [ "$(uname -s)" = "Darwin" ]; then
            if ask_permission "Homebrew isn't installed. Install Homebrew first (official installer)? [Y/n]"; then
                NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" \
                    || die "Homebrew installation failed."
                load_brew_env || die "Homebrew installed but not found. Open a new Terminal and re-run."
                brew install python || die "Homebrew could not install Python."
            else
                die "Python 3.9+ is required. Install from https://www.python.org/downloads/ and re-run."
            fi
        elif command -v apt-get >/dev/null 2>&1; then
            say "${CYAN}⚙️ Installing Python via apt...${RESET}"
            sudo apt-get update && sudo apt-get install -y python3 python3-venv python3-pip || die "apt could not install Python."
        elif command -v dnf >/dev/null 2>&1; then
            sudo dnf install -y python3 python3-pip || die "dnf could not install Python."
        else
            die "Could not auto-install Python on this system. Please install Python 3.9+ and re-run."
        fi
        hash -r
        load_brew_env || true
        PYTHON_BIN="$(find_python || true)"
        [ -n "$PYTHON_BIN" ] || die "Python was installed but isn't on PATH yet. Open a NEW Terminal and re-run."
    else
        die "Python 3.9+ is required to continue."
    fi
fi
say "${GREEN}✔ Using Python:${RESET} $($PYTHON_BIN --version 2>&1) ($(command -v "$PYTHON_BIN"))"

# ------------------------------------------------------------------ 2. App files
PRIVATEDESK_HOME="$HOME/.privatedesk"
INSTALL_DIR="$PRIVATEDESK_HOME/app"
mkdir -p "$PRIVATEDESK_HOME" || die "Cannot create $PRIVATEDESK_HOME"

SCRIPT_SOURCE="${BASH_SOURCE[0]:-}"
if [ -n "$SCRIPT_SOURCE" ] && [ -f "$SCRIPT_SOURCE" ]; then
    CURRENT_DIR="$(cd "$(dirname "$SCRIPT_SOURCE")" && pwd)"
else
    CURRENT_DIR="$(pwd)"
fi

if [ -f "$CURRENT_DIR/cli.py" ] && [ -f "$CURRENT_DIR/requirements.txt" ]; then
    APP_DIR="$CURRENT_DIR"
    say "${GREEN}✔ Running from local project:${RESET} $APP_DIR"
else
    APP_DIR="$INSTALL_DIR"
    say "${CYAN}⚙️ Setting up application directory at:${RESET} $APP_DIR"
    GOT_APP=0
    if command -v git >/dev/null 2>&1; then
        if [ -d "$APP_DIR/.git" ]; then
            git -C "$APP_DIR" pull --ff-only >/dev/null 2>&1 && GOT_APP=1
        else
            rm -rf "$APP_DIR"
            git clone --depth 1 "$REPO_GIT" "$APP_DIR" >/dev/null 2>&1 && GOT_APP=1
        fi
    fi
    if [ "$GOT_APP" -ne 1 ] || [ ! -f "$APP_DIR/cli.py" ]; then
        mkdir -p "$APP_DIR"
        for f in $APP_FILES; do
            curl -fsSL "$REPO_RAW/$f" -o "$APP_DIR/$f" || die "Could not download $f. Check your internet connection."
        done
    fi
    [ -f "$APP_DIR/cli.py" ] || die "cli.py is missing after download."
fi

# ------------------------------------------------------------------ 3. Virtual environment
VENV_DIR="$PRIVATEDESK_HOME/venv"
VENV_PYTHON="$VENV_DIR/bin/python"
if [ ! -x "$VENV_PYTHON" ]; then
    say "${CYAN}⚙️ Creating virtual environment at ~/.privatedesk/venv...${RESET}"
    rm -rf "$VENV_DIR"
    if ! "$PYTHON_BIN" -m venv "$VENV_DIR" >/dev/null 2>&1; then
        rm -rf "$VENV_DIR"
        if ! "$PYTHON_BIN" -m venv --without-pip "$VENV_DIR" >/dev/null 2>&1; then
            say "${YELLOW}On Debian/Ubuntu this usually means: sudo apt install python3-venv${RESET}"
            die "Could not create a virtual environment with $PYTHON_BIN."
        fi
    fi
fi
[ -x "$VENV_PYTHON" ] || die "Virtual environment is missing $VENV_PYTHON"

# ------------------------------------------------------------------ 4. Dependencies
say "${CYAN}📦 Installing dependencies (pypdf, python-pptx, requests)...${RESET}"
"$VENV_PYTHON" -m pip --version >/dev/null 2>&1 || "$VENV_PYTHON" -m ensurepip --default-pip >/dev/null 2>&1
"$VENV_PYTHON" -m pip install --quiet --disable-pip-version-check --upgrade pip >/dev/null 2>&1 || true
"$VENV_PYTHON" -m pip install --quiet --disable-pip-version-check -r "$APP_DIR/requirements.txt" \
    || die "Dependency installation failed. Check your internet connection / proxy and re-run."

# ------------------------------------------------------------------ 5. Ollama + model
say "${CYAN}🧠 Checking local AI engine...${RESET}"
# PRIVATEDESK_SKIP_OLLAMA=1 skips the Ollama install + model download (used by CI).
if [ "${PRIVATEDESK_SKIP_OLLAMA:-}" != "1" ] && ! command -v ollama >/dev/null 2>&1; then
    say "${YELLOW}⚠️ Ollama is required for 100% offline, on-device AI.${RESET}"
    if ask_permission "Install Ollama automatically? [Y/n]"; then
        if command -v brew >/dev/null 2>&1; then
            say "${CYAN}🍺 Installing Ollama via Homebrew...${RESET}"
            brew install --cask ollama >/dev/null 2>&1 || brew install ollama || say "${YELLOW}Homebrew could not install Ollama; get it at https://ollama.com${RESET}"
        else
            say "${CYAN}⚙️ Installing Ollama (official installer)...${RESET}"
            curl -fsSL https://ollama.com/install.sh | sh || say "${YELLOW}Ollama install failed; get it at https://ollama.com${RESET}"
        fi
        hash -r
    else
        say "${DIM}Skipping Ollama. PrivateDesk will offer to install it the first time you ask a question.${RESET}"
    fi
fi

OLLAMA_BIN=""
if [ "${PRIVATEDESK_SKIP_OLLAMA:-}" != "1" ]; then
    OLLAMA_BIN="$(command -v ollama || true)"
    [ -z "$OLLAMA_BIN" ] && [ -x "/Applications/Ollama.app/Contents/Resources/ollama" ] && OLLAMA_BIN="/Applications/Ollama.app/Contents/Resources/ollama"
fi

if [ -n "$OLLAMA_BIN" ]; then
    say "${GREEN}✔ Found Ollama.${RESET} Making sure Qwen 2.5 (1.5B) is ready..."
    if ! curl -s http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
        say "${CYAN}⚙️ Starting local Ollama service...${RESET}"
        if [ "$(uname -s)" = "Darwin" ] && [ -d "/Applications/Ollama.app" ]; then
            open -a Ollama
        else
            nohup "$OLLAMA_BIN" serve >/dev/null 2>&1 &
        fi
        for _ in $(seq 1 15); do
            curl -s http://127.0.0.1:11434/api/tags >/dev/null 2>&1 && break
            sleep 1
        done
    fi
    "$OLLAMA_BIN" pull qwen2.5:1.5b || say "${YELLOW}Model download didn't finish; PrivateDesk will retry automatically on first use.${RESET}"
fi

# ------------------------------------------------------------------ 6. Launcher
BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR" || die "Cannot create $BIN_DIR"
WRAPPER_PATH="$BIN_DIR/privatedesk"

cat > "$WRAPPER_PATH" <<EOF
#!/usr/bin/env bash
exec "$VENV_PYTHON" "$APP_DIR/cli.py" "\$@"
EOF
chmod +x "$WRAPPER_PATH"
say "${GREEN}✔ Created executable at:${RESET} $WRAPPER_PATH"

if [ -d "/usr/local/bin" ] && [ -w "/usr/local/bin" ]; then
    ln -sf "$WRAPPER_PATH" "/usr/local/bin/privatedesk" 2>/dev/null && \
        say "${GREEN}✔ Linked to /usr/local/bin/privatedesk${RESET}"
fi

# ------------------------------------------------------------------ 7. PATH
PATH_LINE='export PATH="$HOME/.local/bin:$PATH"'
export PATH="$HOME/.local/bin:$PATH"

add_path_to_rc() {
    local rc="$1"
    touch "$rc" 2>/dev/null || return 0
    if ! grep -qF "$PATH_LINE" "$rc" 2>/dev/null; then
        printf '\n# PrivateDesk CLI\n%s\n' "$PATH_LINE" >> "$rc"
        say "${GREEN}✔ Added ~/.local/bin to PATH in $rc${RESET}"
    fi
}

# Always configure the user's login shell (create the rc file if it doesn't exist yet),
# plus any other common rc files that already exist.
case "$(basename "${SHELL:-}")" in
    zsh)  add_path_to_rc "$HOME/.zshrc" ;;
    bash) [ "$(uname -s)" = "Darwin" ] && add_path_to_rc "$HOME/.bash_profile" || add_path_to_rc "$HOME/.bashrc" ;;
    *)    [ "$(uname -s)" = "Darwin" ] && add_path_to_rc "$HOME/.zshrc" || add_path_to_rc "$HOME/.profile" ;;
esac
for rc in "$HOME/.zshrc" "$HOME/.bashrc" "$HOME/.bash_profile" "$HOME/.profile"; do
    [ -f "$rc" ] && add_path_to_rc "$rc"
done

say "${CYAN}==========================================================${RESET}"
say "${BOLD}  🎉 PrivateDesk CLI Installation Complete!${RESET}"
say "${CYAN}==========================================================${RESET}"
echo ""
say "Start it now (works in this window; new windows pick up PATH automatically):"
say "  ${BOLD}${GREEN}privatedesk${RESET}            (Open interactive terminal assistant)"
say "  ${BOLD}${GREEN}privatedesk --help${RESET}     (View command reference)"
echo ""
say "Useful Commands:"
say "  • ${CYAN}privatedesk \"What is the laptop loan policy?\"${RESET}"
say "  • ${CYAN}pbpaste | privatedesk${RESET}  (Analyze copied Jira ticket or error log)"
say "  • ${CYAN}privatedesk --docs${RESET}     (List loaded documents)"
say "  • ${CYAN}privatedesk --uninstall${RESET} (Remove everything)"
say "${CYAN}==========================================================${RESET}"
say "${DIM}If 'privatedesk' says 'command not found' in this exact window, run: exec \$SHELL -l${RESET}"
