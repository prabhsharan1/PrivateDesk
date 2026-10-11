#!/usr/bin/env bash
# ==============================================================================
# PrivateDesk — 1-Line Terminal CLI Installer for macOS
# ==============================================================================

set -e

BOLD="\033[1m"
GREEN="\033[32m"
CYAN="\033[36m"
YELLOW="\033[33m"
RESET="\033[0m"

echo -e "${CYAN}==========================================================${RESET}"
echo -e "${BOLD}  🚀 Installing PrivateDesk Terminal AI Assistant${RESET}"
echo -e "${CYAN}==========================================================${RESET}"

# Helper to prompt user even when piped via curl | bash
ask_permission() {
    local prompt_msg="$1"
    local default_ans="${2:-y}"
    local user_reply=""
    if [ -t 0 ]; then
        read -p "$prompt_msg " -r user_reply
    elif [ -e /dev/tty ]; then
        read -p "$prompt_msg " -r user_reply < /dev/tty || user_reply="$default_ans"
    else
        user_reply="$default_ans"
    fi
    user_reply="${user_reply:-$default_ans}"
    [[ "$user_reply" =~ ^[Yy]$ ]]
}

# 1. Check & Install Python 3
PYTHON_BIN=""
if command -v python3 &>/dev/null; then
    PYTHON_BIN="python3"
elif command -v python &>/dev/null; then
    PYTHON_BIN="python"
fi

if [ -z "$PYTHON_BIN" ]; then
    echo -e "${YELLOW}⚠️ Python 3.10+ is required but not installed.${RESET}"
    if ask_permission "Would you like PrivateDesk to install Python 3 for you now? [Y/n]"; then
        if command -v brew &>/dev/null; then
            echo -e "${CYAN}🍺 Installing Python via Homebrew...${RESET}"
            brew install python
            PYTHON_BIN="python3"
        elif [ "$(uname -s)" = "Darwin" ]; then
            echo -e "${CYAN}⚙️ Triggering Xcode Command Line Tools install...${RESET}"
            xcode-select --install || true
            echo -e "${YELLOW}Please complete the system dialog and rerun this installer.${RESET}"
            exit 1
        elif command -v apt-get &>/dev/null; then
            echo -e "${CYAN}⚙️ Installing Python via apt...${RESET}"
            sudo apt-get update && sudo apt-get install -y python3 python3-venv python3-pip
            PYTHON_BIN="python3"
        fi
    else
        echo -e "${RED}Python 3 is required to continue. Installation cancelled.${RESET}"
        exit 1
    fi
fi
echo -e "${GREEN}✔ Detected Python:${RESET} $($PYTHON_BIN --version)"

# 2. Determine Installation Directory
INSTALL_DIR="$HOME/.privatedesk/app"
SCRIPT_SOURCE="${BASH_SOURCE[0]}"

# Check if running from a local git/repo clone or piped via curl
if [ -n "$SCRIPT_SOURCE" ] && [ -f "$SCRIPT_SOURCE" ] && [ "$(dirname "$SCRIPT_SOURCE")" != "." ]; then
    CURRENT_DIR="$(cd "$(dirname "$SCRIPT_SOURCE")" && pwd)"
else
    CURRENT_DIR="$(pwd)"
fi

if [ -f "$CURRENT_DIR/cli.py" ]; then
    APP_DIR="$CURRENT_DIR"
    echo -e "${GREEN}✔ Running from local project:${RESET} $APP_DIR"
else
    APP_DIR="$INSTALL_DIR"
    echo -e "${CYAN}⚙️ Setting up application directory at:${RESET} $APP_DIR"
    mkdir -p "$APP_DIR"
    # Download latest release files if installed via pipe
    if command -v git &>/dev/null && git clone --depth 1 https://github.com/prabhsharan1/PrivateDesk.git "$APP_DIR" 2>/dev/null; then
        echo -e "${GREEN}✔ Successfully cloned repository.${RESET}"
    else
        curl -fsSL https://raw.githubusercontent.com/prabhsharan1/PrivateDesk/main/cli.py -o "$APP_DIR/cli.py" 2>/dev/null || true
        curl -fsSL https://raw.githubusercontent.com/prabhsharan1/PrivateDesk/main/parser.py -o "$APP_DIR/parser.py" 2>/dev/null || true
        curl -fsSL https://raw.githubusercontent.com/prabhsharan1/PrivateDesk/main/retriever.py -o "$APP_DIR/retriever.py" 2>/dev/null || true
        curl -fsSL https://raw.githubusercontent.com/prabhsharan1/PrivateDesk/main/storage.py -o "$APP_DIR/storage.py" 2>/dev/null || true
        curl -fsSL https://raw.githubusercontent.com/prabhsharan1/PrivateDesk/main/llm_engine.py -o "$APP_DIR/llm_engine.py" 2>/dev/null || true
        curl -fsSL https://raw.githubusercontent.com/prabhsharan1/PrivateDesk/main/requirements.txt -o "$APP_DIR/requirements.txt" 2>/dev/null || true
    fi
fi

# 3. Setup Virtual Environment
VENV_DIR="$HOME/.privatedesk/venv"
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${CYAN}⚙️ Creating virtual environment at ~/.privatedesk/venv...${RESET}"
    mkdir -p "$HOME/.privatedesk"
    $PYTHON_BIN -m venv "$VENV_DIR"
fi

VENV_PYTHON="$VENV_DIR/bin/python"
VENV_PIP="$VENV_DIR/bin/pip"

# 4. Install Dependencies
echo -e "${CYAN}📦 Installing dependencies (pypdf, python-pptx, requests)...${RESET}"
"$VENV_PIP" install --quiet --upgrade pip
"$VENV_PIP" install --quiet -r "$APP_DIR/requirements.txt"

# 5. Check & Provision Local AI Engine (Ollama + Qwen 2.5)
echo -e "${CYAN}🧠 Checking local AI engine...${RESET}"
if ! command -v ollama &>/dev/null; then
    echo -e "${YELLOW}⚠️ Ollama is required for 100% offline, on-device AI inference.${RESET}"
    if ask_permission "Would you like PrivateDesk to install Ollama for you now? [Y/n]"; then
        if command -v brew &>/dev/null; then
            echo -e "${CYAN}🍺 Installing Ollama via Homebrew...${RESET}"
            brew install --cask ollama || brew install ollama
        else
            echo -e "${CYAN}⚙️ Downloading and installing Ollama...${RESET}"
            curl -fsSL https://ollama.com/install.sh | sh
        fi
    else
        echo -e "${YELLOW}ℹ️ Skipping Ollama install. You can manually install it anytime from https://ollama.com${RESET}"
    fi
fi

if command -v ollama &>/dev/null; then
    echo -e "${GREEN}✔ Found Ollama.${RESET} Ensuring Qwen 2.5 (1.5B) model is ready..."
    # Start Ollama service if not already responding
    if ! curl -s http://127.0.0.1:11434/api/tags &>/dev/null; then
        echo -e "${CYAN}⚙️ Starting local Ollama service...${RESET}"
        if [ "$(uname -s)" = "Darwin" ] && [ -d "/Applications/Ollama.app" ]; then
            open -a Ollama
        else
            ollama serve &>/dev/null &
        fi
        sleep 3
    fi
    ollama pull qwen2.5:1.5b || true
fi

# 6. Create Global Executable Wrapper
BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"
WRAPPER_PATH="$BIN_DIR/privatedesk"

cat << EOF > "$WRAPPER_PATH"
#!/usr/bin/env bash
exec "$VENV_PYTHON" "$APP_DIR/cli.py" "\$@"
EOF

chmod +x "$WRAPPER_PATH"
echo -e "${GREEN}✔ Created executable at:${RESET} $WRAPPER_PATH"

# Optional: Symlink to /usr/local/bin so it is in standard PATH immediately
if [ -w "/usr/local/bin" ]; then
    ln -sf "$WRAPPER_PATH" "/usr/local/bin/privatedesk" 2>/dev/null || true
    echo -e "${GREEN}✔ Linked to /usr/local/bin/privatedesk (globally accessible).${RESET}"
fi

# 7. Ensure ~/.local/bin is permanently in PATH across shells
export PATH="$HOME/.local/bin:$PATH"
for rc in "$HOME/.zshrc" "$HOME/.bashrc" "$HOME/.profile"; do
    if [ -f "$rc" ]; then
        if ! grep -q 'export PATH="$HOME/.local/bin:$PATH"' "$rc"; then
            echo -e '\n# PrivateDesk CLI\nexport PATH="$HOME/.local/bin:$PATH"' >> "$rc"
            echo -e "${GREEN}✔ Added ~/.local/bin to $rc PATH.${RESET}"
        fi
    fi
done

echo -e "${CYAN}==========================================================${RESET}"
echo -e "${BOLD}  🎉 PrivateDesk CLI Installation Complete!${RESET}"
echo -e "${CYAN}==========================================================${RESET}"
echo ""
echo -e "To start using PrivateDesk immediately, run:"
echo -e "  ${BOLD}${GREEN}privatedesk${RESET}            (Open interactive terminal assistant)"
echo -e "  ${BOLD}${GREEN}privatedesk --help${RESET}     (View command reference)"
echo ""
echo -e "Useful Commands:"
echo -e "  • ${CYAN}privatedesk \"What is the laptop loan policy?\"${RESET}"
echo -e "  • ${CYAN}pbpaste | privatedesk${RESET}  (Analyze copied Jira ticket or error log)"
echo -e "  • ${CYAN}privatedesk --docs${RESET}     (List loaded documents)"
echo -e "  • ${CYAN}privatedesk --clear${RESET}    (Purge local cache)"
echo -e "${CYAN}==========================================================${RESET}"
