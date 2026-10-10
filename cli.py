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
import readline
from pathlib import Path

from parser import parse_uploaded_file
from retriever import DocumentRetriever
from llm_engine import LLMEngine

VERSION = "2.0.0"

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
    # Unescape backslash-escaped characters (e.g. \ , \[, \])
    path_str = re.sub(r"\\(.)", r"\1", path_str)
    return os.path.expanduser(path_str)


def print_banner(retriever: DocumentRetriever):
    """Displays the Claude Code inspired welcome banner."""
    docs = retriever.list_documents()
    total_chunks = len(retriever.chunks)
    
    print(f"{CYAN}╭──────────────────────────────────────────────────────────────╮{RESET}")
    print(f"{CYAN}│{RESET}  {BOLD}PrivateDesk CLI{RESET} {DIM}v{VERSION}{RESET} — 100% Offline AI Assistant (Qwen 2.5)   {CYAN}│{RESET}")
    print(f"{CYAN}│{RESET}  Commands: {YELLOW}/upload <file>{RESET}, {YELLOW}/docs{RESET}, {YELLOW}/clear{RESET}, {YELLOW}/help{RESET}, {YELLOW}/exit{RESET}           {CYAN}│{RESET}")
    print(f"{CYAN}╰──────────────────────────────────────────────────────────────╯{RESET}")
    
    if docs:
        print(f"{DIM}[Vault: {len(docs)} document(s) loaded • {total_chunks} indexed chunks]{RESET}\n")
    else:
        print(f"{DIM}[Vault is empty. Drag & drop a PDF/PPTX or type /upload to begin]{RESET}\n")


def handle_upload(file_input, retriever: DocumentRetriever):
    """Processes one or more uploaded files."""
    if isinstance(file_input, list):
        raw_paths = file_input
    elif isinstance(file_input, str):
        file_input = file_input.strip()
        if not file_input:
            print(f"{YELLOW}Usage: /upload <path-to-pdf-or-pptx>{RESET}")
            print(f"{DIM}Tip: You can drag and drop files from Finder directly into this window.{RESET}")
            return
        # If the entire input is already a valid path (with spaces unescaped), use it directly
        single_candidate = clean_finder_path(file_input)
        if Path(single_candidate).exists():
            raw_paths = [single_candidate]
        else:
            try:
                raw_paths = shlex.split(file_input)
            except Exception:
                raw_paths = [file_input]
    else:
        return

    for raw in raw_paths:
        clean_path = clean_finder_path(raw)
        if not clean_path:
            continue

        p = Path(clean_path)
        if not p.exists():
            print(f"{RED}❌ File not found:{RESET} {clean_path}")
            continue

        filename = p.name
        ext = p.suffix.lower()
        if ext not in [".pdf", ".pptx"]:
            print(f"{YELLOW}⚠️ Unsupported file type:{RESET} '{filename}'. Supported: .pdf, .pptx")
            continue

        print(f"{CYAN}⏳ Indexing {filename}...{RESET}")
        try:
            pages = parse_uploaded_file(str(p), filename)
            retriever.add_document(filename, pages)
            doc_meta = retriever.documents.get(filename, {})
            chunks = doc_meta.get("total_chunks", 0)
            unit = "slides" if ext == ".pptx" else "pages"
            print(f"{GREEN}✔ Successfully indexed:{RESET} {BOLD}{filename}{RESET} ({len(pages)} {unit}, {chunks} chunks)")
        except Exception as e:
            print(f"{RED}❌ Error parsing {filename}:{RESET} {e}")


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


def handle_clear(retriever: DocumentRetriever):
    """Clears all indexed documents from memory and disk."""
    retriever.clear_all()
    print(f"{GREEN}✔ Knowledge Vault cleared.{RESET} All documents purged from local cache.")


def print_help():
    """Prints help message."""
    print(f"\n{BOLD}PrivateDesk Command Reference:{RESET}")
    print(f"  {YELLOW}/upload <path>{RESET}   Add PDF or PPTX files (drag & drop from Finder supported)")
    print(f"  {YELLOW}/docs{RESET}            List all loaded documents and chunk stats")
    print(f"  {YELLOW}/clear{RESET}           Purge all loaded documents from memory and disk")
    print(f"  {YELLOW}/help{RESET}            Display this help screen")
    print(f"  {YELLOW}/exit{RESET}            Quit PrivateDesk\n")
    print(f"{BOLD}Terminal Shortcuts:{RESET}")
    print(f"  • One-shot query:   {CYAN}privatedesk \"What is the laptop loan policy?\"{RESET}")
    print(f"  • Clipboard pipe:   {CYAN}pbpaste | privatedesk{RESET}\n")


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
            elif cmd in ["/help", "help", "?"]:
                print_help()
            elif cmd in ["/docs", "/list", "docs", "list"]:
                handle_docs(retriever)
            elif cmd in ["/clear", "clear"]:
                handle_clear(retriever)
            elif cmd.startswith("/upload") or cmd.startswith("/add"):
                parts = user_input.split(maxsplit=1)
                file_arg = parts[1] if len(parts) > 1 else ""
                handle_upload(file_arg, retriever)
            elif user_input.startswith("/"):
                print(f"{YELLOW}Unknown command:{RESET} {user_input}. Type {CYAN}/help{RESET} for options.")
            else:
                answer_query(user_input, retriever, engine)

        except (KeyboardInterrupt, EOFError):
            print(f"\n{DIM}Exiting PrivateDesk.{RESET}")
            break


def main():
    retriever = DocumentRetriever(persistent=True)
    engine = LLMEngine()

    # Mode 1: Pipe / Stdin Mode (e.g. pbpaste | privatedesk)
    if not sys.stdin.isatty():
        piped_input = sys.stdin.read().strip()
        additional_query = " ".join(sys.argv[1:]).strip()
        combined_query = f"{additional_query}\n\nContext from input:\n{piped_input}" if additional_query else piped_input
        answer_query(combined_query, retriever, engine)
        sys.exit(0)

    # Mode 2: Command-Line Flags
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
        elif first_arg in ["--clear", "-c"]:
            handle_clear(retriever)
            sys.exit(0)
        elif first_arg in ["--upload", "-u"]:
            if len(sys.argv) > 2:
                handle_upload(sys.argv[2:], retriever)
            else:
                print(f"{YELLOW}Usage: privatedesk --upload <path-to-file>{RESET}")
            sys.exit(0)
        else:
            # Mode 3: One-shot CLI query: privatedesk "What is the policy?"
            one_shot_query = " ".join(sys.argv[1:])
            answer_query(one_shot_query, retriever, engine)
            sys.exit(0)

    # Mode 4: Interactive REPL Mode
    run_repl(retriever, engine)


if __name__ == "__main__":
    main()
