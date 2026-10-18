#!/usr/bin/env bash
# ==============================================================================
# PrivateDesk — 1-Line Terminal CLI Uninstaller for macOS / Linux
# ==============================================================================

set -e

RED="\033[31m"
GREEN="\033[32m"
CYAN="\033[36m"
YELLOW="\033[33m"
BOLD="\033[1m"
DIM="\033[2m"
RESET="\033[0m"

echo -e "${CYAN}==========================================================${RESET}"
echo -e "${BOLD}  🗑️  Uninstalling PrivateDesk CLI${RESET}"
echo -e "${CYAN}==========================================================${RESET}"

# Confirm with the user (works interactively and when piped through `curl | bash`)
read_input() {
    local prompt_msg="$1" default_ans="$2" reply=""
    if [ -t 0 ]; then
        read -r -p "$prompt_msg " reply
    elif [ -r /dev/tty ]; then
        read -r -p "$prompt_msg " reply < /dev/tty || reply="$default_ans"
    else
        reply="$default_ans"
    fi
    echo "${reply:-$default_ans}"
}

REMOVE_APP=0
REMOVE_VENV=0
REMOVE_CACHE=0
REMOVE_MODEL=0
REMOVE_OLLAMA=0

if [ "${PRIVATEDESK_YES:-}" = "1" ]; then
    # Non-interactive / CI mode: clean removal of PrivateDesk app, venv & cache
    REMOVE_APP=1
    REMOVE_VENV=1
    REMOVE_CACHE=1
else
    echo -e "Please choose an uninstallation option:\n"
    echo -e "  ${BOLD}[1] Complete / Everything${RESET}"
    echo -e "      • Remove PrivateDesk application & launcher"
    echo -e "      • Remove Python virtual environment & dependencies"
    echo -e "      • Remove Knowledge Vault & document cache"
    echo -e "      • Remove Qwen 2.5 AI model from Ollama (frees ~1GB)"
    echo -e "      • Uninstall Ollama application\n"
    echo -e "  ${BOLD}[2] PrivateDesk Only${RESET} ${DIM}(Keep Ollama & AI Models)${RESET}  ${CYAN}[Default]${RESET}"
    echo -e "      • Remove PrivateDesk app, launcher, venv, and cache"
    echo -e "      • Preserves Ollama and AI models for other applications\n"
    echo -e "  ${BOLD}[3] Custom / Selective Uninstall${RESET}"
    echo -e "      • Choose individually what to delete or keep\n"
    echo -e "  ${BOLD}[4] Cancel${RESET}\n"

    CHOICE="$(read_input "${BOLD}Enter choice [1-4] (default: 2):${RESET}" "2")"

    case "$CHOICE" in
        1|[Aa][Ll][Ll])
            CONFIRM="$(read_input "${YELLOW}⚠️ This will remove PrivateDesk, dependencies, Qwen model, and Ollama. Proceed? [y/N]:${RESET}" "n")"
            if [[ ! "$CONFIRM" =~ ^[Yy] ]]; then
                echo -e "${YELLOW}Uninstallation cancelled.${RESET}"
                exit 0
            fi
            REMOVE_APP=1
            REMOVE_VENV=1
            REMOVE_CACHE=1
            REMOVE_MODEL=1
            REMOVE_OLLAMA=1
            ;;
        2|[Dd][Ee][Ff][Aa][Uu][Ll][Tt]|"")
            CONFIRM="$(read_input "${YELLOW}Remove PrivateDesk, its virtual environment and cached documents? [y/N]:${RESET}" "n")"
            if [[ ! "$CONFIRM" =~ ^[Yy] ]]; then
                echo -e "${YELLOW}Uninstallation cancelled.${RESET}"
                exit 0
            fi
            REMOVE_APP=1
            REMOVE_VENV=1
            REMOVE_CACHE=1
            ;;
        3|[Cc][Uu][Ss][Tt][Oo][Mm]|[Ss][Ee][Ll][Ee][Cc][Tt][Ii][Vv][Ee])
            echo -e "\n${CYAN}Select components to remove:${RESET}"
            ANS_APP="$(read_input "  Remove PrivateDesk application and CLI launcher? [Y/n]:" "y")"
            [[ "$ANS_APP" =~ ^[Nn] ]] || REMOVE_APP=1

            ANS_VENV="$(read_input "  Remove Python virtual environment & dependencies (~/.privatedesk/venv)? [Y/n]:" "y")"
            [[ "$ANS_VENV" =~ ^[Nn] ]] || REMOVE_VENV=1

            ANS_CACHE="$(read_input "  Remove Knowledge Vault & document cache (store.json)? [Y/n]:" "y")"
            [[ "$ANS_CACHE" =~ ^[Nn] ]] || REMOVE_CACHE=1

            ANS_MODEL="$(read_input "  Remove Qwen 2.5 AI model from Ollama (frees ~1GB)? [y/N]:" "n")"
            [[ "$ANS_MODEL" =~ ^[Yy] ]] && REMOVE_MODEL=1

            ANS_OLLAMA="$(read_input "  Uninstall Ollama application entirely? [y/N]:" "n")"
            [[ "$ANS_OLLAMA" =~ ^[Yy] ]] && REMOVE_OLLAMA=1
            ;;
        *)
            echo -e "${YELLOW}Uninstallation cancelled.${RESET}"
            exit 0
            ;;
    esac
fi

echo ""

# 1. Remove Qwen AI Model from Ollama
if [ "$REMOVE_MODEL" = "1" ]; then
    OLLAMA_BIN="$(command -v ollama || true)"
    [ -z "$OLLAMA_BIN" ] && [ -x "/Applications/Ollama.app/Contents/Resources/ollama" ] && OLLAMA_BIN="/Applications/Ollama.app/Contents/Resources/ollama"
    if [ -n "$OLLAMA_BIN" ]; then
        echo -e "${CYAN}⚙️ Removing Qwen 2.5 AI model from Ollama...${RESET}"
        "$OLLAMA_BIN" rm qwen2.5:1.5b 2>/dev/null || true
        "$OLLAMA_BIN" rm qwen2.5:1.5b-instruct 2>/dev/null || true
        echo -e "${GREEN}✔ Removed:${RESET} Qwen 2.5 AI model"
    else
        echo -e "${DIM}Ollama binary not found in PATH; skipping model removal.${RESET}"
    fi
fi

# 2. Uninstall Ollama Application
if [ "$REMOVE_OLLAMA" = "1" ]; then
    echo -e "${CYAN}⚙️ Uninstalling Ollama application...${RESET}"
    pkill -f Ollama 2>/dev/null || killall Ollama 2>/dev/null || true
    if [ "$(uname -s)" = "Darwin" ]; then
        if command -v brew >/dev/null 2>&1; then
            brew uninstall --cask ollama 2>/dev/null || brew uninstall ollama 2>/dev/null || true
        fi
        if [ -d "/Applications/Ollama.app" ]; then
            rm -rf "/Applications/Ollama.app"
            echo -e "${GREEN}✔ Removed:${RESET} /Applications/Ollama.app"
        fi
    else
        systemctl stop ollama 2>/dev/null || true
        systemctl disable ollama 2>/dev/null || true
        rm -f /etc/systemd/system/ollama.service 2>/dev/null || true
        rm -f /usr/local/bin/ollama 2>/dev/null || true
        rm -rf /usr/share/ollama 2>/dev/null || true
    fi
    rm -rf "$HOME/.ollama" 2>/dev/null || true
    echo -e "${GREEN}✔ Removed:${RESET} Ollama application and data"
fi

# 3. Clean up shell rc PATH entries helper
clean_shell_rc() {
    local rc_file="$1"
    if [ -f "$rc_file" ] && grep -q 'PrivateDesk CLI' "$rc_file"; then
        sed -i.bak '/# PrivateDesk CLI/d' "$rc_file" 2>/dev/null || true
        sed -i.bak '/export PATH="\$HOME\/.local\/bin:\$PATH"/d' "$rc_file" 2>/dev/null || true
        rm -f "${rc_file}.bak"
        echo -e "${GREEN}✔ Cleaned PATH entry from:${RESET} $rc_file"
    fi
}

# 4. Remove executables and symlinks
if [ "$REMOVE_APP" = "1" ]; then
    echo -e "${CYAN}⚙️ Removing executables and launchers...${RESET}"
    if [ -f "$HOME/.local/bin/privatedesk" ]; then
        rm -f "$HOME/.local/bin/privatedesk"
        echo -e "${GREEN}✔ Removed:${RESET} $HOME/.local/bin/privatedesk"
    fi

    if [ -f "/usr/local/bin/privatedesk" ] || [ -L "/usr/local/bin/privatedesk" ]; then
        rm -f "/usr/local/bin/privatedesk" 2>/dev/null || true
        echo -e "${GREEN}✔ Removed:${RESET} /usr/local/bin/privatedesk"
    fi

    clean_shell_rc "$HOME/.zshrc"
    clean_shell_rc "$HOME/.bashrc"
    clean_shell_rc "$HOME/.bash_profile"
    clean_shell_rc "$HOME/.profile"

    if [ -d "$HOME/.privatedesk/app" ]; then
        rm -rf "$HOME/.privatedesk/app"
        echo -e "${GREEN}✔ Removed:${RESET} $HOME/.privatedesk/app"
    fi
fi

# 5. Remove Python virtual environment and dependencies
if [ "$REMOVE_VENV" = "1" ]; then
    if [ -d "$HOME/.privatedesk/venv" ]; then
        echo -e "${CYAN}⚙️ Removing Python virtual environment & dependencies...${RESET}"
        rm -rf "$HOME/.privatedesk/venv"
        echo -e "${GREEN}✔ Removed:${RESET} $HOME/.privatedesk/venv"
    fi
fi

# 6. Remove Knowledge Vault and cached documents
if [ "$REMOVE_CACHE" = "1" ]; then
    if [ -f "$HOME/.privatedesk/store.json" ]; then
        echo -e "${CYAN}⚙️ Removing Knowledge Vault cache...${RESET}"
        rm -f "$HOME/.privatedesk/store.json"
        echo -e "${GREEN}✔ Removed:${RESET} $HOME/.privatedesk/store.json"
    fi
    rm -rf "$HOME/.privatedesk/data" 2>/dev/null || true
fi

# 7. Clean ~/.privatedesk directory if empty or if everything was uninstalled
if [ -d "$HOME/.privatedesk" ]; then
    if [ "$REMOVE_APP" = "1" ] && [ "$REMOVE_VENV" = "1" ] && [ "$REMOVE_CACHE" = "1" ]; then
        rm -rf "$HOME/.privatedesk"
        echo -e "${GREEN}✔ Removed directory:${RESET} $HOME/.privatedesk"
    elif [ -z "$(ls -A "$HOME/.privatedesk" 2>/dev/null)" ]; then
        rm -rf "$HOME/.privatedesk"
        echo -e "${GREEN}✔ Removed directory:${RESET} $HOME/.privatedesk"
    fi
fi

echo -e "${CYAN}==========================================================${RESET}"
echo -e "${BOLD}${GREEN}  🎉 Uninstallation complete.${RESET}"
echo -e "${CYAN}==========================================================${RESET}"
if [ "$REMOVE_OLLAMA" = "0" ] && [ "$REMOVE_MODEL" = "0" ]; then
    echo -e "${DIM}Note: Ollama and your AI models were preserved for other applications.${RESET}\n"
else
    echo ""
fi
