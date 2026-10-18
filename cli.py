#!/usr/bin/env python3
"""
PrivateDesk — 100% Offline On-Device AI Terminal Assistant.
Inspired by Claude Code and Ollama.
Zero cloud telemetry. Zero token limits. Fast on Apple Silicon.
"""

import sys
import os
import re
import shlex
try:
    import readline  # Not available on Windows
except ImportError:
    readline = None
import shutil
from pathlib import Path

from parser import parse_uploaded_file
from retriever import DocumentRetriever
from llm_engine import LLMEngine

VERSION = "2.0.0"

# Windows consoles: enable ANSI colors and force UTF-8 so emoji/box characters never crash printing
if os.name == "nt":
    os.system("")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ANSI Terminal Colors & Styling
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
RED = "\033[31m"
RESET = "\033[0m"


def clean_finder_path(path_str: str) -> str:
    """
    Cleans paths dragged and dropped from macOS Finder.
    Handles escaped spaces, quotes, and backslashes.
    """
    path_str = path_str.strip()
    if not path_str:
        return ""
    # Strip enclosing quotes if present
    if (path_str.startswith("'") and path_str.endswith("'")) or \
       (path_str.startswith('"') and path_str.endswith('"')):
        path_str = path_str[1:-1]
    # Unescape backslash-escaped characters (e.g. \ , \[, \]) -- macOS/Linux only.
    # On Windows the backslash is the path separator and must be preserved.
    if os.name != "nt":
        path_str = re.sub(r"\\(.)", r"\1", path_str)
    return os.path.expanduser(path_str)


COMMANDS = [
    "/upload",
    "/add",
    "/docs",
    "/list",
    "/reset",
    "/purge",
    "/uninstall",
    "/help",
    "/exit",
    "clear",
    "exit",
    "quit"
]


def setup_autocomplete():
    """Sets up Tab completion for slash commands."""
    try:
        def completer(text, state):
            options = [cmd for cmd in COMMANDS if cmd.startswith(text)]
            if state < len(options):
                return options[state] + " "
            return None

        readline.set_completer(completer)
        if "libedit" in readline.__doc__:
            readline.parse_and_bind("bind ^I rl_complete")
        else:
            readline.parse_and_bind("tab: complete")
    except Exception:
        pass


def print_banner(retriever: DocumentRetriever):
    """Displays the Claude Code inspired welcome banner and quick command menu."""
    docs = retriever.list_documents()
    total_chunks = len(retriever.chunks)
    
    print(f"{CYAN}╭──────────────────────────────────────────────────────────────╮{RESET}")
    print(f"{CYAN}│{RESET}  {BOLD}PrivateDesk CLI{RESET} {DIM}v{VERSION}{RESET} — 100% Offline AI Assistant (Qwen 2.5)   {CYAN}│{RESET}")
    print(f"{CYAN}╰──────────────────────────────────────────────────────────────╯{RESET}")
    
    if docs:
        print(f"  {GREEN}●{RESET} {BOLD}Vault:{RESET} {len(docs)} document(s) loaded • {total_chunks} indexed chunks")
    else:
        print(f"  {YELLOW}○{RESET} {DIM}Knowledge Vault is empty.{RESET}")

    print(f"\n{BOLD}⚡ Quick Commands:{RESET}")
    print(f"  {YELLOW}/upload <path>{RESET}   Index PDF, PPTX, or entire folder (drag & drop)")
    print(f"  {YELLOW}/docs{RESET}            List loaded documents & slide/page counts")
    print(f"  {YELLOW}/reset{RESET}           Purge all loaded documents from cache")
    print(f"  {YELLOW}clear{RESET}            Clear terminal screen")
    print(f"  {YELLOW}/help{RESET}            Show full command guide & clipboard tricks")
    print(f"  {YELLOW}/exit{RESET}            Exit PrivateDesk (or press Ctrl+D)")
    print(f"\n{DIM}Tip: You can drag & drop any file or folder directly into this window!{RESET}\n")


def index_single_file(p: Path, retriever: DocumentRetriever, prefix: str = "") -> bool:
    """Helper to parse and index a single PDF or PPTX file."""
    filename = p.name
    ext = p.suffix.lower()
    if ext not in [".pdf", ".pptx"]:
        print(f"{YELLOW}⚠️ Unsupported file type:{RESET} '{filename}'. Supported: .pdf, .pptx")
        return False

    print(f"{CYAN}⏳ {prefix}Indexing {filename}...{RESET}")
    try:
        pages = parse_uploaded_file(str(p), filename)
        retriever.add_document(filename, pages)
        doc_meta = retriever.documents.get(filename, {})
        chunks = doc_meta.get("total_chunks", 0)
        unit = "slides" if ext == ".pptx" else "pages"
        print(f"{GREEN}✔ Successfully indexed:{RESET} {BOLD}{filename}{RESET} ({len(pages)} {unit}, {chunks} chunks)")
        return True
    except Exception as e:
        print(f"{RED}❌ Error parsing {filename}:{RESET} {e}")
        return False


def handle_upload(file_input, retriever: DocumentRetriever):
    """Processes one or more uploaded files or entire directories."""
    if isinstance(file_input, str):
        # Strip extraneous /upload or /add tags if user pasted path and command together
        clean_input = re.sub(r"(^|\s)(/upload|/add)(\s|$)", " ", file_input, flags=re.IGNORECASE).strip()
    else:
        clean_input = file_input

    if isinstance(clean_input, list):
        raw_paths = clean_input
    elif isinstance(clean_input, str):
        if not clean_input:
            print(f"{YELLOW}Usage: /upload <path-to-file-or-folder>{RESET}")
            print(f"{DIM}Tip: You can drag and drop files or folders directly into this window.{RESET}")
            return
        # If the entire input is already a valid path (with spaces unescaped), use it directly
        single_candidate = clean_finder_path(clean_input)
        if Path(single_candidate).exists():
            raw_paths = [single_candidate]
        else:
            try:
                raw_paths = shlex.split(clean_input, posix=(os.name != "nt"))
            except Exception:
                raw_paths = [clean_input]
    else:
        return

    for raw in raw_paths:
        clean_path = clean_finder_path(raw)
        if not clean_path:
            continue

        p = Path(clean_path)
        if not p.exists():
            print(f"{RED}❌ Path not found:{RESET} {clean_path}")
            continue

        if p.is_dir():
            # Recursively find all supported documents (.pdf, .pptx)
            sub_files = []
            for item in sorted(p.rglob("*")):
                if (item.is_file() and 
                    item.suffix.lower() in [".pdf", ".pptx"] and 
                    not item.name.startswith("~$") and 
                    not item.name.startswith("._")):
                    sub_files.append(item)

            if not sub_files:
                print(f"{YELLOW}⚠️ No .pdf or .pptx files found in directory:{RESET} {p.name}")
                continue

            print(f"\n{CYAN}📁 Found {len(sub_files)} document(s) in {BOLD}{p.name}{RESET}{CYAN}. Indexing...{RESET}")
            indexed_count = 0
            for i, f in enumerate(sub_files, 1):
                if index_single_file(f, retriever, prefix=f"[{i}/{len(sub_files)}] "):
                    indexed_count += 1
            print(f"{GREEN}🎉 Finished indexing directory:{RESET} {BOLD}{p.name}{RESET} ({indexed_count}/{len(sub_files)} indexed)\n")
        else:
            index_single_file(p, retriever)


def handle_docs(retriever: DocumentRetriever):
    """Displays loaded documents in the vault."""
    docs = retriever.list_documents()
    if not docs:
        print(f"{YELLOW}Knowledge Vault is empty.{RESET} Use {CYAN}/upload <file>{RESET} to add training PDFs or PPTXs.")
        return

    print(f"\n{BOLD}📚 Loaded Documents in Knowledge Vault:{RESET}")
    print(f"{DIM}──────────────────────────────────────────────────────────────{RESET}")
    for idx, d in enumerate(docs, 1):
        fn = d["filename"]
        pages = d["total_pages"]
        chunks = d["total_chunks"]
        unit = "slides" if fn.lower().endswith(".pptx") else "pages"
        print(f" {idx}. {BOLD}{fn}{RESET} — {pages} {unit} ({chunks} chunks)")
    print(f"{DIM}──────────────────────────────────────────────────────────────{RESET}")
    print(f"Total: {len(docs)} document(s), {len(retriever.chunks)} total chunks.\n")


def handle_clear_screen(retriever: DocumentRetriever):
    """Clears the terminal screen and redisplays the banner."""
    os.system("cls" if os.name == "nt" else "clear")
    print_banner(retriever)


def handle_purge(retriever: DocumentRetriever, force: bool = False):
    """Safely purges all indexed documents from memory and disk cache."""
    docs = retriever.list_documents()
    if not docs:
        print(f"{YELLOW}Knowledge Vault is already empty.{RESET}")
        return

    if not force:
        try:
            confirm = input(
                f"{YELLOW}⚠️ Purge all {len(docs)} document(s) from your Knowledge Vault?\n"
                f"{DIM}   (Tip: Type 'clear' if you only wanted to clear the terminal screen!){RESET}\n"
                f"   Type 'y' to confirm purge [y/N]: "
            ).strip().lower()
            if confirm not in ["y", "yes"]:
                print(f"{DIM}Purge cancelled. Your documents are safe.{RESET}\n")
                return
        except (KeyboardInterrupt, EOFError):
            print(f"\n{DIM}Purge cancelled.{RESET}\n")
            return

    retriever.clear_all()
    print(f"{GREEN}✔ Knowledge Vault cleared.{RESET} All documents purged from local cache.\n")


def handle_uninstall():
    """Interactive uninstaller supporting complete or selective component removal."""
    if os.name == "nt":
        print(f"\n{YELLOW}Windows locks active executables while PrivateDesk is running.{RESET}")
        print("To uninstall PrivateDesk (with options for Python, dependencies, Ollama & Qwen):")
        print(f"  {CYAN}irm https://raw.githubusercontent.com/prabhsharan1/PrivateDesk/main/uninstall.ps1 | iex{RESET}\n")
        try:
            launch = input("Launch the PowerShell uninstaller now? [Y/n]: ").strip().lower()
            if launch in ["", "y", "yes"]:
                import subprocess
                subprocess.Popen([
                    "powershell.exe",
                    "-ExecutionPolicy", "Bypass",
                    "-Command",
                    "Start-Sleep -Seconds 1; irm https://raw.githubusercontent.com/prabhsharan1/PrivateDesk/main/uninstall.ps1 | iex"
                ])
                sys.exit(0)
        except Exception:
            pass
        return

    print(f"\n{CYAN}=========================================================={RESET}")
    print(f"{BOLD}  🗑️  PrivateDesk Uninstallation Manager{RESET}")
    print(f"{CYAN}=========================================================={RESET}")
    print("\nPlease choose an uninstallation option:\n")
    print(f"  {BOLD}[1] Complete / Everything{RESET}")
    print(f"      • Remove PrivateDesk application & launcher")
    print(f"      • Remove Python virtual environment & dependencies")
    print(f"      • Remove Knowledge Vault & document cache")
    print(f"      • Remove Qwen 2.5 AI model from Ollama (frees ~1GB)")
    print(f"      • Uninstall Ollama application\n")
    print(f"  {BOLD}[2] PrivateDesk Only{RESET} {DIM}(Keep Ollama & AI Models){RESET}  {CYAN}[Default]{RESET}")
    print(f"      • Remove PrivateDesk app, launcher, venv, and cache")
    print(f"      • Preserves Ollama and AI models for other applications\n")
    print(f"  {BOLD}[3] Custom / Selective Uninstall{RESET}")
    print(f"      • Choose individually what to delete or keep\n")
    print(f"  {BOLD}[4] Cancel{RESET}\n")

    try:
        choice = input(f"{BOLD}Enter choice [1-4] (default: 2): {RESET}").strip()
    except (KeyboardInterrupt, EOFError):
        print(f"\n{DIM}Uninstallation cancelled.{RESET}\n")
        return

    if not choice:
        choice = "2"

    remove_app = False
    remove_venv = False
    remove_cache = False
    remove_model = False
    remove_ollama = False

    if choice in ["1", "all"]:
        try:
            confirm = input(
                f"{YELLOW}⚠️ This will remove PrivateDesk, dependencies, Qwen model, and Ollama.\n"
                f"   Proceed with complete uninstall? [y/N]: {RESET}"
            ).strip().lower()
            if confirm not in ["y", "yes"]:
                print(f"{DIM}Uninstallation cancelled.{RESET}\n")
                return
        except (KeyboardInterrupt, EOFError):
            print(f"\n{DIM}Uninstallation cancelled.{RESET}\n")
            return
        remove_app = True
        remove_venv = True
        remove_cache = True
        remove_model = True
        remove_ollama = True

    elif choice in ["2", "default"]:
        try:
            confirm = input(
                f"{YELLOW}Remove PrivateDesk, its virtual environment and cached documents? [y/N]: {RESET}"
            ).strip().lower()
            if confirm not in ["y", "yes"]:
                print(f"{DIM}Uninstallation cancelled.{RESET}\n")
                return
        except (KeyboardInterrupt, EOFError):
            print(f"\n{DIM}Uninstallation cancelled.{RESET}\n")
            return
        remove_app = True
        remove_venv = True
        remove_cache = True

    elif choice in ["3", "custom", "selective"]:
        print(f"\n{CYAN}Select components to remove:{RESET}")
        try:
            ans = input("  Remove PrivateDesk application and CLI launcher? [Y/n]: ").strip().lower()
            remove_app = ans not in ["n", "no"]

            ans = input("  Remove Python virtual environment & dependencies (~/.privatedesk/venv)? [Y/n]: ").strip().lower()
            remove_venv = ans not in ["n", "no"]

            ans = input("  Remove Knowledge Vault & document cache (store.json)? [Y/n]: ").strip().lower()
            remove_cache = ans not in ["n", "no"]

            ans = input("  Remove Qwen 2.5 AI model from Ollama (frees ~1GB)? [y/N]: ").strip().lower()
            remove_model = ans in ["y", "yes"]

            ans = input("  Uninstall Ollama application entirely? [y/N]: ").strip().lower()
            remove_ollama = ans in ["y", "yes"]
        except (KeyboardInterrupt, EOFError):
            print(f"\n{DIM}Uninstallation cancelled.{RESET}\n")
            return
    else:
        print(f"{DIM}Uninstallation cancelled.{RESET}\n")
        return

    import subprocess
    home = Path.home()

    # 1. Remove Qwen model
    if remove_model:
        print(f"\n{CYAN}⚙️ Removing Qwen 2.5 AI model from Ollama...{RESET}")
        try:
            subprocess.run(["ollama", "rm", "qwen2.5:1.5b"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["ollama", "rm", "qwen2.5:1.5b-instruct"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"{GREEN}✔ Removed Qwen 2.5 AI model from Ollama.{RESET}")
        except Exception:
            pass

    # 2. Uninstall Ollama
    if remove_ollama:
        print(f"{CYAN}⚙️ Uninstalling Ollama application...{RESET}")
        try:
            subprocess.run(["pkill", "-f", "Ollama"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if sys.platform == "darwin":
                subprocess.run(["brew", "uninstall", "--cask", "ollama"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                ollama_app = Path("/Applications/Ollama.app")
                if ollama_app.exists():
                    shutil.rmtree(ollama_app, ignore_errors=True)
            ollama_dir = home / ".ollama"
            if ollama_dir.exists():
                shutil.rmtree(ollama_dir, ignore_errors=True)
            print(f"{GREEN}✔ Removed Ollama application & models.{RESET}")
        except Exception:
            pass

    # 3. Remove launchers & PATH
    if remove_app:
        bin_wrapper = home / ".local" / "bin" / "privatedesk"
        if bin_wrapper.exists():
            bin_wrapper.unlink()
            print(f"{GREEN}✔ Removed executable:{RESET} {bin_wrapper}")

        usr_local_wrapper = Path("/usr/local/bin/privatedesk")
        if usr_local_wrapper.exists() or usr_local_wrapper.is_symlink():
            try:
                usr_local_wrapper.unlink()
                print(f"{GREEN}✔ Removed symlink:{RESET} {usr_local_wrapper}")
            except Exception:
                pass

        for rc_name in [".zshrc", ".bashrc", ".bash_profile", ".profile"]:
            rc_path = home / rc_name
            if rc_path.exists():
                try:
                    lines = rc_path.read_text(encoding="utf-8").splitlines()
                    filtered = [l for l in lines if "PrivateDesk CLI" not in l and '.local/bin' not in l]
                    if len(filtered) != len(lines):
                        rc_path.write_text("\n".join(filtered) + "\n", encoding="utf-8")
                        print(f"{GREEN}✔ Cleaned PATH entry from:{RESET} ~/{rc_name}")
                except Exception:
                    pass

        app_dir = home / ".privatedesk" / "app"
        if app_dir.exists():
            shutil.rmtree(app_dir, ignore_errors=True)

    # 4. Remove venv & dependencies
    if remove_venv:
        venv_dir = home / ".privatedesk" / "venv"
        if venv_dir.exists():
            shutil.rmtree(venv_dir, ignore_errors=True)
            print(f"{GREEN}✔ Removed Python virtual environment & dependencies:{RESET} {venv_dir}")

    # 5. Remove Cache
    if remove_cache:
        store_file = home / ".privatedesk" / "store.json"
        if store_file.exists():
            store_file.unlink()
            print(f"{GREEN}✔ Removed Knowledge Vault cache:{RESET} {store_file}")
        data_dir = home / ".privatedesk" / "data"
        if data_dir.exists():
            shutil.rmtree(data_dir, ignore_errors=True)

    # Clean ~/.privatedesk directory if empty or if full wipe
    privatedesk_dir = home / ".privatedesk"
    if privatedesk_dir.exists():
        remaining = list(privatedesk_dir.iterdir())
        if not remaining or (remove_app and remove_venv and remove_cache):
            shutil.rmtree(privatedesk_dir, ignore_errors=True)
            print(f"{GREEN}✔ Removed directory:{RESET} {privatedesk_dir}")

    print(f"\n{GREEN}🎉 Uninstallation complete.{RESET}\n")
    if not remove_ollama and not remove_model:
        print(f"{DIM}Note: Ollama and your AI models were preserved for other applications.{RESET}\n")
    sys.exit(0)


def print_help():
    """Prints comprehensive help message."""
    print(f"\n{BOLD}PrivateDesk Command Reference:{RESET}")
    print(f"{DIM}──────────────────────────────────────────────────────────────{RESET}")
    print(f"  {YELLOW}/upload <path>{RESET}   Index PDF, PPTX, or entire folder (drag & drop supported)")
    print(f"  {YELLOW}/docs{RESET}            List all loaded documents and chunk stats")
    print(f"  {YELLOW}/reset{RESET}           Purge all loaded documents from memory and disk")
    print(f"  {YELLOW}clear{RESET}            Clear terminal screen (or type 'cls')")
    print(f"  {YELLOW}/help{RESET}            Display this help screen")
    print(f"  {YELLOW}/uninstall{RESET}       Uninstall PrivateDesk (complete or selective options)")
    print(f"  {YELLOW}/exit{RESET}            Quit PrivateDesk (or press Ctrl+D)\n")
    print(f"{BOLD}💡 Shortcuts & Power Tricks:{RESET}")
    print(f"  • {BOLD}Drag & Drop:{RESET}        Drag any file or folder directly into the prompt!")
    print(f"  • {BOLD}Clear Screen:{RESET}       Type {YELLOW}clear{RESET} to wipe the terminal without touching your vault")
    print(f"  • {BOLD}One-shot query:{RESET}      {CYAN}privatedesk \"What is the laptop loan policy?\"{RESET}")
    print(f"  • {BOLD}Mac Clipboard pipe:{RESET}  {CYAN}pbpaste | privatedesk{RESET}")
    print(f"  • {BOLD}Win Clipboard pipe:{RESET}  {CYAN}Get-Clipboard | privatedesk{RESET}")
    print(f"  • {BOLD}Pipe server logs:{RESET}    {CYAN}cat error.log | privatedesk \"Explain this error\"{RESET}")
    print(f"  • {BOLD}Tab Auto-complete:{RESET}   Type {YELLOW}/{RESET} and hit {BOLD}[Tab]{RESET} to complete commands")
    print(f"{DIM}──────────────────────────────────────────────────────────────{RESET}\n")


def answer_query(query: str, retriever: DocumentRetriever, engine: LLMEngine):
    """Searches documents and prints the AI response with citations."""
    query = query.strip()
    if not query:
        return

    if not retriever.chunks:
        print(f"\n{YELLOW}⚠️ No documents are currently loaded in your vault.{RESET}")
        print(f"Please use {CYAN}/upload <file.pdf or file.pptx>{RESET} to index training materials first.\n")
        return

    print(f"\n{DIM}Thinking...{RESET}")
    top_chunks = retriever.search(query, top_k=3)
    reply, sources = engine.generate(query, top_chunks)

    print(f"{DIM}──────────────────────────────────────────────────────────────{RESET}")
    print(f"{reply}")
    
    if sources:
        print(f"\n{CYAN}📚 Source Citations:{RESET}")
        seen = set()
        for s in sources:
            key = f"{s['filename']}_p{s['page']}"
            if key not in seen:
                seen.add(key)
                unit = "Slide" if s['filename'].lower().endswith('.pptx') else "Page"
                print(f"  • {BOLD}{s['filename']}{RESET} ({unit} {s['page']})")
    print(f"{DIM}──────────────────────────────────────────────────────────────{RESET}\n")


def run_repl(retriever: DocumentRetriever, engine: LLMEngine):
    """Runs the interactive REPL loop."""
    setup_autocomplete()
    print_banner(retriever)

    while True:
        try:
            user_input = input(f"{BOLD}> {RESET}").strip()
            if not user_input:
                continue

            # Command Routing
            cmd = user_input.lower()
            if cmd in ["/exit", "exit", "quit", ":q"]:
                print(f"{DIM}Goodbye!{RESET}")
                break
            elif cmd in ["clear", "cls", "/cls"]:
                handle_clear_screen(retriever)
            elif cmd in ["/reset", "/purge", "/clear-vault", "/clear"]:
                handle_purge(retriever)
            elif cmd in ["/uninstall", "uninstall"]:
                handle_uninstall()
            elif cmd in ["/help", "help", "?"]:
                print_help()
            elif cmd in ["/docs", "/list", "docs", "list"]:
                handle_docs(retriever)
            elif "/upload" in cmd or "/add" in cmd:
                # Handle /upload anywhere in the input (beginning, middle, or end)
                file_arg = re.sub(r"(^|\s)(/upload|/add)(\s|$)", " ", user_input, flags=re.IGNORECASE).strip()
                handle_upload(file_arg, retriever)
            else:
                # Check if user directly dragged/pasted a valid file or folder path without typing /upload
                candidate_path = clean_finder_path(user_input)
                if candidate_path and Path(candidate_path).exists():
                    print(f"{CYAN}📁 Detected input path:{RESET} {candidate_path}")
                    handle_upload(candidate_path, retriever)
                elif user_input.startswith("/"):
                    # Check if it looks like an intended filesystem path that couldn't be found
                    if user_input.startswith(("/Users", "/home", "/var", "/tmp", "~", "C:", "D:")) or "/" in user_input[1:] or "\\" in user_input:
                        print(f"{RED}❌ Path not found:{RESET} {user_input}")
                    else:
                        print(f"{YELLOW}Unknown command:{RESET} {user_input}. Type {CYAN}/help{RESET} for options.")
                else:
                    answer_query(user_input, retriever, engine)

        except (KeyboardInterrupt, EOFError):
            print(f"\n{DIM}Exiting PrivateDesk.{RESET}")
            break


def main():
    retriever = DocumentRetriever(persistent=True)
    engine = LLMEngine()

    # Mode 1: Command-Line Flags (always take priority, even when stdin is not a terminal)
    if len(sys.argv) > 1:
        first_arg = sys.argv[1]
        if first_arg in ["--help", "-h"]:
            print_banner(retriever)
            print_help()
            sys.exit(0)
        elif first_arg in ["--version", "-v"]:
            print(f"PrivateDesk CLI v{VERSION}")
            sys.exit(0)
        elif first_arg in ["--docs", "-d"]:
            handle_docs(retriever)
            sys.exit(0)
        elif first_arg in ["--clear", "-c", "--reset", "-r", "--purge"]:
            handle_purge(retriever, force=True)
            sys.exit(0)
        elif first_arg in ["--uninstall"]:
            handle_uninstall()
            sys.exit(0)
        elif first_arg in ["--upload", "-u"]:
            if len(sys.argv) > 2:
                handle_upload(sys.argv[2:], retriever)
            else:
                print(f"{YELLOW}Usage: privatedesk --upload <path-to-file>{RESET}")
            sys.exit(0)

    # Mode 2: Pipe / Stdin Mode (e.g. pbpaste | privatedesk "Explain this")
    if not sys.stdin.isatty():
        piped_input = sys.stdin.read().strip()
        additional_query = " ".join(sys.argv[1:]).strip()
        combined_query = f"{additional_query}\n\nContext from input:\n{piped_input}" if additional_query and piped_input else (additional_query or piped_input)
        answer_query(combined_query, retriever, engine)
        sys.exit(0)

    # Mode 3: One-shot CLI query: privatedesk "What is the policy?"
    if len(sys.argv) > 1:
        answer_query(" ".join(sys.argv[1:]), retriever, engine)
        sys.exit(0)

    # Mode 4: Interactive REPL Mode
    run_repl(retriever, engine)


if __name__ == "__main__":
    main()
