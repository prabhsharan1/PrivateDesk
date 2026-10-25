"""
Persistent Document Storage for PrivateDesk CLI.
Saves and loads indexed documents and chunks across terminal sessions in ~/.privatedesk/store.json.
Supports process-safe atomic writes and multi-terminal freshness checks.
"""

import os
import json
import time
from pathlib import Path

DEFAULT_STORAGE_DIR = Path.home() / ".privatedesk"
DEFAULT_STORE_FILE = DEFAULT_STORAGE_DIR / "store.json"


def ensure_storage_dir(storage_dir: Path | None = None) -> Path:
    """Ensures the storage directory exists with proper permissions."""
    target_dir = storage_dir or DEFAULT_STORAGE_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir


def get_store_mtime(store_file: Path = DEFAULT_STORE_FILE) -> float:
    """Returns modification timestamp of store.json, or 0.0 if not present."""
    try:
        return store_file.stat().st_mtime if store_file.exists() else 0.0
    except OSError:
        return 0.0


def save_store(documents: dict, chunks: list, store_file: Path = DEFAULT_STORE_FILE) -> None:
    """
    Serializes documents metadata and chunks to store.json.
    Uses process-isolated temporary file before atomic os.replace to prevent
    concurrent terminals from colliding.
    """
    ensure_storage_dir(store_file.parent)
    data = {
        "version": "1.0",
        "updated_at": time.time(),
        "documents": documents,
        "chunks": chunks
    }
    # PID-isolated temp file prevents concurrent process write collisions
    temp_file = store_file.parent / f"{store_file.name}.tmp.{os.getpid()}"
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(temp_file, store_file)
    finally:
        if temp_file.exists():
            try:
                temp_file.unlink()
            except OSError:
                pass


def load_store(store_file: Path = DEFAULT_STORE_FILE) -> tuple[dict, list]:
    """Loads documents metadata and chunks from store.json."""
    if not store_file.exists():
        return {}, []
    try:
        with open(store_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("documents", {}), data.get("chunks", [])
    except Exception:
        return {}, []


def clear_store(store_file: Path = DEFAULT_STORE_FILE) -> bool:
    """Removes the store.json file to reset all saved documents."""
    if store_file.exists():
        try:
            store_file.unlink()
            return True
        except OSError:
            return False
    return True
