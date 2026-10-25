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
import json
import threading
import subprocess
import urllib.request
try:
    import readline  # Not available on Windows
except ImportError:
    readline = None
import shutil
from pathlib import Path

from parser import parse_uploaded_file, DocumentParser
from retriever import DocumentRetriever
from llm_engine import LLMEngine

def load_local_version_info():
    """Loads version and release metadata from version.json."""
    version_file = Path(__file__).resolve().parent / "version.json"
    if version_file.exists():
        try:
            with open(version_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "version": "2.1.0",
        "title": "PrivateDesk",
        "highlights": [],
        "date": "2026-10-23"
    }

LOCAL_VERSION_INFO = load_local_version_info()
VERSION = LOCAL_VERSION_INFO.get("version", "2.1.0")

def parse_version_tuple(v_str):
    """Extracts integer tuple from version string for semantic comparison."""
    nums = re.findall(r"\d+", str(v_str or ""))
    return tuple(map(int, nums)) if nums else (0, 0, 0)

# Remote version URL (Raw GitHub has no rate limits)
REMOTE_VERSION_URL = "https://raw.githubusercontent.com/prabhsharan1/PrivateDesk/main/version.json"

_update_lock = threading.Lock()
_cached_remote_info = None
_update_check_done = False
_update_thread = None

def fetch_remote_version_info(timeout: float = 1.0):
    """Fetches version.json from GitHub raw repository with GitHub API fallback."""
    try:
        req = urllib.request.Request(
            REMOTE_VERSION_URL,
            headers={"User-Agent": "PrivateDesk-CLI"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode("utf-8"))
    except Exception:
        pass

    # Fallback to GitHub API (which base64-decodes content if raw CDN is temporarily caching)
    try:
        import base64
        api_url = "https://api.github.com/repos/prabhsharan1/PrivateDesk/contents/version.json"
        req = urllib.request.Request(api_url, headers={"User-Agent": "PrivateDesk-CLI"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                payload = json.loads(resp.read().decode("utf-8"))
                if payload.get("encoding") == "base64" and payload.get("content"):
                    raw_text = base64.b64decode(payload["content"]).decode("utf-8")
                    return json.loads(raw_text)
    except Exception:
        pass

    return None

def _async_update_worker():
    global _cached_remote_info, _update_check_done
    info = fetch_remote_version_info(timeout=1.0)
    with _update_lock:
        _cached_remote_info = info
        _update_check_done = True

def start_background_update_check():
    """Starts non-blocking background thread to check for updates."""
    global _update_thread
    _update_thread = threading.Thread(target=_async_update_worker, daemon=True)
    _update_thread.start()

def get_update_status(wait_timeout: float = 0.5):
    """
    Returns (status, info_dict) where status is:
      'available' : remote version is higher than local
      'up_to_date': remote version is <= local
      'unknown'   : check timed out or offline
    """
    global _update_thread
    if _update_thread and _update_thread.is_alive() and wait_timeout > 0:
        _update_thread.join(timeout=wait_timeout)

    with _update_lock:
        info = _cached_remote_info

    if not info:
        return ("unknown", None)

    remote_v = info.get("version", "")
    if parse_version_tuple(remote_v) > parse_version_tuple(VERSION):
        return ("available", info)
    return ("up_to_date", info)

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
    "/update",
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

    status, info = get_update_status(wait_timeout=0.4)
    if status == "available":
        remote_v = info.get("version", "")
        update_line = f"  {YELLOW}/update{RESET}                Update PrivateDesk {GREEN}(★ Update available: v{remote_v}){RESET}"
    elif status == "up_to_date":
        update_line = f"  {YELLOW}/update{RESET}                Update PrivateDesk {DIM}(Up to date){RESET}"
    else:
        update_line = f"  {YELLOW}/update{RESET}                Check for updates / update PrivateDesk"

    print(f"\n{BOLD}⚡ Quick Commands:{RESET}")
    print(f"  {YELLOW}/upload <path or url>{RESET}   Index PDF, PPTX, or Confluence / web URL")
    print(f"  {YELLOW}/docs{RESET}                  List loaded documents & section/page counts")
    print(update_line)
    print(f"  {YELLOW}/reset{RESET}                 Purge all loaded documents from cache")
    print(f"  {YELLOW}clear{RESET}                  Clear terminal screen")
    print(f"  {YELLOW}/help{RESET}                  Show full command guide & clipboard tricks")
    print(f"  {YELLOW}/exit{RESET}                  Exit PrivateDesk (or press Ctrl+D)")
    print(f"\n{DIM}Tip: You can drag & drop files, folders, or paste Confluence/web links directly!{RESET}\n")


def index_web_url(url: str, retriever: DocumentRetriever) -> bool:
    """Fetches a web page or Confluence article, splits by sub-parts/headings, and indexes into the vault."""
    print(f"\n{CYAN}🌐 Fetching web document:{RESET} {url} ...")
    try:
        web_data = DocumentParser.parse_url(url)
        doc_title = web_data["doc_title"]
        sections = web_data["sections"]
        is_targeted = web_data["is_targeted"]
        target_anchor = web_data["target_anchor"]

        pages = [
            {
                "page": s["section_num"],
                "section_title": s["title"],
                "url": s["url"],
                "text": f"## {s['title']}\n\n{s['text']}"
            }
            for s in sections
        ]

        if is_targeted:
            target_topic = sections[0]["title"]
            filename = f"[Web] {doc_title} - {target_topic}"
        else:
            filename = f"[Web] {doc_title}"

        retriever.add_document(filename, pages, doc_type="web", url=url)
        total_chunks = retriever.documents.get(filename, {}).get("total_chunks", 0)

        if is_targeted:
            target_topic = sections[0]["title"]
            print(f"\n{GREEN}✔ Targeted Topic Extracted:{RESET} {BOLD}\"{target_topic}\"{RESET}")
            print(f"  {CYAN}📍 Document:{RESET} {doc_title}")
            print(f"  {CYAN}📍 Source URL:{RESET} {url}")
            print(f"\n{BOLD}📑 Extracted Section:{RESET}")
            print(f"  • {BOLD}{target_topic}{RESET} ({total_chunks} chunks)")
            print(f"\n{GREEN}🎉 Only this targeted topic was added to the Knowledge Vault.{RESET}")
            print(f"{DIM}💡 You can now ask questions specifically about \"{target_topic}\"!{RESET}\n")
        else:
            print(f"\n{GREEN}✔ Web Document Extracted:{RESET} {BOLD}{doc_title}{RESET}")
            print(f"  {CYAN}📍 Source URL:{RESET} {url}")
            if web_data.get("target_not_found") and target_anchor:
                print(f"  {YELLOW}⚠️ Notice: Anchor '#{target_anchor}' was not found on the page; indexed all sections instead.{RESET}")
            print(f"\n{BOLD}📑 Extracted {len(sections)} Sub-topics / Sections:{RESET}")
            for s in sections:
                s_chunks = len(retriever.chunk_text(s["text"]))
                print(f"  {s['section_num']}. {BOLD}{s['title']}{RESET} ({s_chunks} chunks)")
            print(f"\n{GREEN}🎉 Successfully indexed into Knowledge Vault ({total_chunks} total chunks).{RESET}")
            first_topic = sections[0]["title"]
            print(f"{DIM}💡 You can now ask questions about any of these topics! (e.g., \"Tell me about {first_topic}\"){RESET}\n")

        return True
    except Exception as e:
        print(f"{RED}❌ Error processing web URL:{RESET} {e}\n")
        return False


def index_single_file(p: Path, retriever: DocumentRetriever, prefix: str = "") -> bool:
    """Helper to parse and index a single PDF or PPTX file."""
    filename = p.name
    ext = p.suffix.lower()
    if ext not in [".pdf", ".pptx"]:
        print(f"{YELLOW}⚠️ Unsupported file type:{RESET} '{filename}'. Supported: .pdf, .pptx, or web URLs")
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
    """Processes one or more uploaded files, directories, or web/Confluence URLs."""
    if isinstance(file_input, str):
        # Strip extraneous /upload or /add tags if user pasted path and command together
        clean_input = re.sub(r"(^|\s)(/upload|/add)(\s|$)", " ", file_input, flags=re.IGNORECASE).strip()
    else:
        clean_input = file_input

    if isinstance(clean_input, list):
        raw_paths = clean_input
    elif isinstance(clean_input, str):
        if not clean_input:
            print(f"{YELLOW}Usage: /upload <path-to-file-or-folder or web-url>{RESET}")
            print(f"{DIM}Tip: You can drag and drop files or paste Confluence/web links directly.{RESET}")
            return
        # If the input is a web URL, handle it directly
        if clean_input.startswith(("http://", "https://")):
            raw_paths = [clean_input]
        # If the entire input is already a valid path (with spaces unescaped), use it directly
        elif Path(clean_finder_path(clean_input)).exists():
            raw_paths = [clean_finder_path(clean_input)]
        else:
            try:
                raw_paths = shlex.split(clean_input, posix=(os.name != "nt"))
            except Exception:
                raw_paths = [clean_input]
    else:
        return

    for raw in raw_paths:
        if raw.startswith(("http://", "https://")):
            index_web_url(raw, retriever)
            continue

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
        print(f"{YELLOW}Knowledge Vault is empty.{RESET} Use {CYAN}/upload <file or url>{RESET} to add training PDFs, PPTXs, or web links.")
        return

    print(f"\n{BOLD}📚 Loaded Documents in Knowledge Vault:{RESET}")
    print(f"{DIM}──────────────────────────────────────────────────────────────{RESET}")
    for idx, d in enumerate(docs, 1):
        fn = d["filename"]
        pages = d["total_pages"]
        chunks = d["total_chunks"]
        if d.get("type") == "web":
            unit = "section" if pages == 1 else "sections"
            print(f" {idx}. 🌐 {BOLD}{fn}{RESET} — {pages} {unit} ({chunks} chunks)")
            if d.get("url"):
                print(f"     {DIM}URL: {d.get('url')}{RESET}")
        else:
            unit = "slides" if fn.lower().endswith(".pptx") else "pages"
            print(f" {idx}. 📄 {BOLD}{fn}{RESET} — {pages} {unit} ({chunks} chunks)")
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


def handle_update_info():
    """Displays release highlights and What's New details."""
    print(f"\n{CYAN}🔍 Checking latest release information from GitHub...{RESET}")
    remote_info = fetch_remote_version_info(timeout=3.0)
    
    if remote_info:
        remote_v = remote_info.get("version", VERSION)
        remote_title = remote_info.get("title", "")
        remote_date = remote_info.get("date", "")
        highlights = remote_info.get("highlights", [])
        is_newer = parse_version_tuple(remote_v) > parse_version_tuple(VERSION)

        if is_newer:
            print(f"\n{CYAN}╭──────────────────────────────────────────────────────────────╮{RESET}")
            print(f"{CYAN}│{RESET}  {BOLD}🌟 PrivateDesk v{remote_v} is Available!{RESET} {DIM}(Installed: v{VERSION}){RESET}   {CYAN}│{RESET}")
            print(f"{CYAN}╰──────────────────────────────────────────────────────────────╯{RESET}")
            if remote_title:
                print(f"  {BOLD}Release:{RESET} {remote_title} {DIM}({remote_date}){RESET}")
            print(f"\n{BOLD}✨ What's New:{RESET}")
            for h in highlights:
                print(f"  {GREEN}•{RESET} {h}")
            print(f"\n{CYAN}👉 To install this update, run:{RESET} {YELLOW}/update{RESET} (or from terminal: {BOLD}privatedesk --update{RESET})\n")
        else:
            print(f"\n{GREEN}✔ You are running the latest version of PrivateDesk (v{VERSION}).{RESET}")
            if remote_title:
                print(f"  {BOLD}Release:{RESET} {remote_title} {DIM}({remote_date}){RESET}")
            if highlights:
                print(f"\n{BOLD}✨ Features & Highlights in v{VERSION}:{RESET}")
                for h in highlights:
                    print(f"  {GREEN}•{RESET} {h}")
            print("")
    else:
        # Offline or couldn't reach GitHub: show local version highlights
        local_highlights = LOCAL_VERSION_INFO.get("highlights", [])
        local_title = LOCAL_VERSION_INFO.get("title", "")
        print(f"\n{YELLOW}ℹ️ Currently offline or GitHub unreachable.{RESET}")
        print(f"Installed Version: {BOLD}v{VERSION}{RESET}")
        if local_title:
            print(f"Title: {local_title}")
        if local_highlights:
            print(f"\n{BOLD}✨ Features in installed v{VERSION}:{RESET}")
            for h in local_highlights:
                print(f"  • {h}")
        print("")


def handle_update(force: bool = False):
    """Updates PrivateDesk to the latest version while preserving vault data."""
    print(f"\n{CYAN}🔄 Checking for updates from GitHub...{RESET}")
    remote_info = fetch_remote_version_info(timeout=3.5)

    remote_v = remote_info.get("version", "") if remote_info else ""
    is_newer = False
    if remote_v:
        is_newer = parse_version_tuple(remote_v) > parse_version_tuple(VERSION)

    if not is_newer and not force:
        if remote_v:
            print(f"\n{GREEN}✔ PrivateDesk is already up to date (v{VERSION}).{RESET}")
            print(f"{DIM}Type {YELLOW}/update --info{RESET}{DIM} to see release highlights.{RESET}")
            print(f"{DIM}(To force a re-download anyway, run: {YELLOW}/update --force{RESET}{DIM}){RESET}\n")
        else:
            print(f"\n{YELLOW}⚠️ Could not connect to GitHub to check for updates.{RESET}")
            print(f"Please check your internet connection and try again.\n")
        return

    target_version = remote_v if remote_v else "latest"
    if is_newer:
        print(f"\n{GREEN}🚀 New version detected:{RESET} {BOLD}v{target_version}{RESET} (currently running v{VERSION})")
    
    if not force:
        try:
            choice = input(f"\nInstall update to v{target_version} now? [Y/n]: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{DIM}Update cancelled.{RESET}")
            return
        if choice and not choice.startswith("y"):
            print(f"{DIM}Update cancelled.{RESET}\n")
            return

    app_dir = Path(__file__).resolve().parent
    repo_raw = "https://raw.githubusercontent.com/prabhsharan1/PrivateDesk/main"
    update_files = ["cli.py", "parser.py", "retriever.py", "storage.py", "llm_engine.py", "version.json", "requirements.txt"]

    print(f"\n{CYAN}📥 Updating PrivateDesk components in:{RESET} {app_dir}")

    updated_ok = False
    # Attempt 1: Git pull if running from a git repository
    if (app_dir / ".git").is_dir() and shutil.which("git"):
        try:
            print(f"  {CYAN}⚙️ Pulling latest changes via git...{RESET}")
            res = subprocess.run(["git", "-C", str(app_dir), "pull", "--ff-only"], capture_output=True, text=True)
            if res.returncode == 0:
                updated_ok = True
                print(f"  {GREEN}✔ Git repository successfully updated.{RESET}")
            else:
                # If pull failed due to local file modifications, sync cleanly to origin/main
                subprocess.run(["git", "-C", str(app_dir), "fetch", "origin", "main"], capture_output=True, check=False)
                res_reset = subprocess.run(["git", "-C", str(app_dir), "reset", "--hard", "origin/main"], capture_output=True, text=True)
                if res_reset.returncode == 0:
                    updated_ok = True
                    print(f"  {GREEN}✔ Git repository successfully updated.{RESET}")
                else:
                    print(f"  {YELLOW}⚠️ Git pull reported:{RESET} {res.stderr.strip() or res.stdout.strip()}")
        except Exception as e:
            print(f"  {YELLOW}⚠️ Git pull failed ({e}); falling back to direct download.{RESET}")

    # Attempt 2: Direct HTTP download from GitHub raw
    if not updated_ok:
        try:
            print(f"  {CYAN}⚙️ Downloading updated components from GitHub...{RESET}")
            for f in update_files:
                url = f"{repo_raw}/{f}"
                req = urllib.request.Request(url, headers={"User-Agent": "PrivateDesk-CLI"})
                with urllib.request.urlopen(req, timeout=8.0) as resp:
                    if resp.status == 200:
                        content = resp.read()
                        with open(app_dir / f, "wb") as out_f:
                            out_f.write(content)
                        print(f"  {GREEN}✔{RESET} Updated {f}")
                    else:
                        raise RuntimeError(f"HTTP {resp.status} for {f}")
            updated_ok = True
        except Exception as e:
            print(f"\n{RED}❌ Failed to download update files:{RESET} {e}")
            print(f"{YELLOW}Your existing installation was left intact.{RESET}\n")
            return

    # Attempt to update dependencies
    req_file = app_dir / "requirements.txt"
    if req_file.exists():
        try:
            print(f"  {CYAN}📦 Checking Python dependencies...{RESET}")
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--quiet", "--disable-pip-version-check", "-r", str(req_file)],
                capture_output=True,
                check=False
            )
            print(f"  {GREEN}✔ Dependencies up to date.{RESET}")
        except Exception:
            pass

    vault_count = 0
    try:
        vault_count = len(DocumentRetriever(persistent=True).list_documents())
    except Exception:
        pass

    print(f"\n{CYAN}=========================================================={RESET}")
    print(f"{BOLD}{GREEN}  🎉 PrivateDesk Successfully Updated to v{target_version}!{RESET}")
    print(f"{CYAN}=========================================================={RESET}")
    print(f"  {GREEN}●{RESET} Knowledge Vault cache preserved ({vault_count} document(s) safe)")
    print(f"  {CYAN}💡 Run '{YELLOW}/update --info{CYAN}' to see what's new!{RESET}\n")

    # Offer to reload immediately
    try:
        restart = input("Restart PrivateDesk now to load the update? [Y/n]: ").strip().lower()
        if not restart or restart.startswith("y"):
            print(f"{CYAN}Restarting PrivateDesk...{RESET}\n")
            os.execv(sys.executable, [sys.executable, str(app_dir / "cli.py")])
    except Exception:
        pass
    print(f"{DIM}Please exit and re-open PrivateDesk to use the updated version.{RESET}\n")


def print_help():
    """Prints comprehensive help message."""
    print(f"\n{BOLD}PrivateDesk Command Reference:{RESET}")
    print(f"{DIM}──────────────────────────────────────────────────────────────{RESET}")
    print(f"  {YELLOW}/upload <path/url>{RESET} Index PDF, PPTX, or Confluence / web URL (supports drag & drop)")
    print(f"  {YELLOW}/docs{RESET}             List all loaded documents and chunk stats")
    print(f"  {YELLOW}/update{RESET}           Check for and install updates to PrivateDesk")
    print(f"  {YELLOW}/update --info{RESET}    Display What's New and release highlights")
    print(f"  {YELLOW}/reset{RESET}            Purge all loaded documents from memory and disk")
    print(f"  {YELLOW}clear{RESET}             Clear terminal screen (or type 'cls')")
    print(f"  {YELLOW}/help{RESET}             Display this help screen")
    print(f"  {YELLOW}/uninstall{RESET}        Uninstall PrivateDesk (complete or selective options)")
    print(f"  {YELLOW}/exit{RESET}             Quit PrivateDesk (or press Ctrl+D)\n")
    print(f"{BOLD}💡 Shortcuts & Power Tricks:{RESET}")
    print(f"  • {BOLD}Drag & Drop / Links:{RESET} Drag files/folders or paste Confluence/web links directly!")
    print(f"  • {BOLD}Targeted Sub-Topics:{RESET} Add #anchor (e.g. #laptop-loans) to index ONLY that topic")
    print(f"  • {BOLD}Release Highlights:{RESET}  Type {YELLOW}/update --info{RESET} to see what's new in the release")
    print(f"  • {BOLD}Clear Screen:{RESET}        Type {YELLOW}clear{RESET} to wipe the terminal without touching your vault")
    print(f"  • {BOLD}One-shot query:{RESET}       {CYAN}privatedesk \"What is the laptop loan policy?\"{RESET}")
    print(f"  • {BOLD}Mac Clipboard pipe:{RESET}   {CYAN}pbpaste | privatedesk{RESET}")
    print(f"  • {BOLD}Win Clipboard pipe:{RESET}   {CYAN}Get-Clipboard | privatedesk{RESET}")
    print(f"  • {BOLD}Pipe server logs:{RESET}     {CYAN}cat error.log | privatedesk \"Explain this error\"{RESET}")
    print(f"  • {BOLD}Tab Auto-complete:{RESET}    Type {YELLOW}/{RESET} and hit {BOLD}[Tab]{RESET} to complete commands")
    print(f"{DIM}──────────────────────────────────────────────────────────────{RESET}\n")


def answer_query(query: str, retriever: DocumentRetriever, engine: LLMEngine):
    """Searches documents and prints the AI response with citations."""
    query = query.strip()
    if not query:
        return

    retriever.ensure_fresh_state()
    if not retriever.chunks:
        print(f"\n{YELLOW}⚠️ No documents are currently loaded in your vault.{RESET}")
        print(f"Please use {CYAN}/upload <file or url>{RESET} to index training materials first.\n")
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
            key = f"{s['filename']}_{s['page']}_{s.get('section_title')}"
            if key not in seen:
                seen.add(key)
                if s.get("section_title"):
                    link_info = f"\n     {DIM}{s['url']}{RESET}" if s.get("url") else ""
                    print(f"  • {BOLD}{s['filename']}{RESET} (Section: \"{s['section_title']}\"){link_info}")
                else:
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
            elif cmd in ["/update --info", "/update -i", "/update info", "update info", "update --info"]:
                handle_update_info()
            elif cmd in ["/update --force", "/update -f"]:
                handle_update(force=True)
            elif cmd in ["/update", "update"]:
                handle_update()
            elif cmd in ["/help", "help", "?"]:
                print_help()
            elif cmd in ["/docs", "/list", "docs", "list"]:
                handle_docs(retriever)
            elif "/upload" in cmd or "/add" in cmd:
                # Handle /upload anywhere in the input (beginning, middle, or end)
                file_arg = re.sub(r"(^|\s)(/upload|/add)(\s|$)", " ", user_input, flags=re.IGNORECASE).strip()
                handle_upload(file_arg, retriever)
            else:
                # Check if user directly pasted a web URL
                if user_input.startswith(("http://", "https://")):
                    print(f"{CYAN}🌐 Detected web URL:{RESET} {user_input}")
                    handle_upload(user_input, retriever)
                # Check if user directly dragged/pasted a valid file or folder path without typing /upload
                else:
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
    # Start non-blocking background check for updates immediately
    start_background_update_check()

    # Fast-path command-line flags that don't need DocumentRetriever or LLMEngine
    if len(sys.argv) > 1:
        first_arg = sys.argv[1]
        if first_arg in ["--version", "-v"]:
            print(f"PrivateDesk CLI v{VERSION}")
            sys.exit(0)
        elif first_arg in ["--update-info", "-ui"]:
            handle_update_info()
            sys.exit(0)
        elif first_arg in ["--update", "-U"]:
            if len(sys.argv) > 2 and sys.argv[2] in ["--info", "-i", "info"]:
                handle_update_info()
            elif len(sys.argv) > 2 and sys.argv[2] in ["--force", "-f", "force"]:
                handle_update(force=True)
            else:
                handle_update()
            sys.exit(0)
        elif first_arg in ["--uninstall"]:
            handle_uninstall()
            sys.exit(0)

    retriever = DocumentRetriever(persistent=True)
    engine = LLMEngine()

    # Mode 1: Command-Line Flags (always take priority, even when stdin is not a terminal)
    if len(sys.argv) > 1:
        first_arg = sys.argv[1]
        if first_arg in ["--help", "-h"]:
            print_banner(retriever)
            print_help()
            sys.exit(0)
        elif first_arg in ["--docs", "-d"]:
            handle_docs(retriever)
            sys.exit(0)
        elif first_arg in ["--clear", "-c", "--reset", "-r", "--purge"]:
            handle_purge(retriever, force=True)
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
