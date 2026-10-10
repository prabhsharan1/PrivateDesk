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

# 1. Check Python
PYTHON_BIN=""
if command -v python3 &>/dev/null; then
    PYTHON_BIN="python3"
elif command -v python &>/dev/null; then
    PYTHON_BIN="python"
else
    echo -e "${YELLOW}❌ Error: Python 3 is required. Please install Python 3.10+.${RESET}"
    exit 1
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

# 5. Check & Pull Local AI Engine (Qwen 2.5 via Ollama)
echo -e "${CYAN}🧠 Checking local AI engine...${RESET}"
if command -v ollama &>/dev/null; then
    echo -e "${GREEN}✔ Found Ollama.${RESET} Ensuring Qwen 2.5 (1.5B) model is ready..."
    ollama pull qwen2.5:1.5b || true
else
    echo -e "${YELLOW}ℹ️ Ollama CLI not found in PATH yet.${RESET}"
    echo -e "   To run 100% offline, download Ollama from: ${BOLD}https://ollama.com${RESET}"
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

# Optional: Try symlinking to /usr/local/bin if writable
if [ -w "/usr/local/bin" ]; then
    ln -sf "$WRAPPER_PATH" "/usr/local/bin/privatedesk" 2>/dev/null || true
fi

# 7. Ensure ~/.local/bin is in PATH in ~/.zshrc
ZSHRC="$HOME/.zshrc"
if [ -f "$ZSHRC" ]; then
    if ! grep -q 'export PATH="$HOME/.local/bin:$PATH"' "$ZSHRC"; then
        echo -e '\n# PrivateDesk CLI\nexport PATH="$HOME/.local/bin:$PATH"' >> "$ZSHRC"
        echo -e "${GREEN}✔ Added ~/.local/bin to ~/.zshrc PATH.${RESET}"
    fi
fi

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
