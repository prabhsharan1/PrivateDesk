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
RESET="\033[0m"

echo -e "${CYAN}==========================================================${RESET}"
echo -e "${BOLD}  🗑️  Uninstalling PrivateDesk CLI${RESET}"
echo -e "${CYAN}==========================================================${RESET}"

# Confirm with user if interactive
if [ -t 0 ]; then
    read -p "Are you sure you want to completely remove PrivateDesk and its local cache? [y/N] " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Uninstallation cancelled.${RESET}"
        exit 0
    fi
fi

# 1. Remove executables and symlinks
echo -e "${CYAN}⚙️ Removing executables...${RESET}"
if [ -f "$HOME/.local/bin/privatedesk" ]; then
    rm -f "$HOME/.local/bin/privatedesk"
    echo -e "${GREEN}✔ Removed:${RESET} $HOME/.local/bin/privatedesk"
fi

if [ -f "/usr/local/bin/privatedesk" ] || [ -L "/usr/local/bin/privatedesk" ]; then
    rm -f "/usr/local/bin/privatedesk" 2>/dev/null || true
    echo -e "${GREEN}✔ Removed:${RESET} /usr/local/bin/privatedesk"
fi

# 2. Remove application directory and virtual environment (~/.privatedesk)
if [ -d "$HOME/.privatedesk" ]; then
    echo -e "${CYAN}⚙️ Removing application files, venv, and cache (~/.privatedesk)...${RESET}"
    rm -rf "$HOME/.privatedesk"
    echo -e "${GREEN}✔ Removed:${RESET} $HOME/.privatedesk"
fi

# 3. Clean up ~/.zshrc or ~/.bashrc PATH entry
clean_shell_rc() {
    local rc_file="$1"
    if [ -f "$rc_file" ] && grep -q 'PrivateDesk CLI' "$rc_file"; then
        sed -i.bak '/# PrivateDesk CLI/d' "$rc_file" 2>/dev/null || true
        sed -i.bak '/export PATH="\$HOME\/.local\/bin:\$PATH"/d' "$rc_file" 2>/dev/null || true
        rm -f "${rc_file}.bak"
        echo -e "${GREEN}✔ Cleaned PATH entry from:${RESET} $rc_file"
    fi
}

clean_shell_rc "$HOME/.zshrc"
clean_shell_rc "$HOME/.bashrc"

echo -e "${CYAN}==========================================================${RESET}"
echo -e "${BOLD}${GREEN}  🎉 PrivateDesk has been completely uninstalled.${RESET}"
echo -e "${CYAN}==========================================================${RESET}"
echo -e "${DIM}Note: If you installed Ollama and want to remove it separately, see https://ollama.com${RESET}\n"
