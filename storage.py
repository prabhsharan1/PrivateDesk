"""
Persistent Document Storage for PrivateDesk CLI.
Saves and loads indexed documents and chunks across terminal sessions in ~/.privatedesk/store.json.
"""

import os
import json
from pathlib import Path

DEFAULT_STORAGE_DIR = Path.home() / ".privatedesk"
DEFAULT_STORE_FILE = DEFAULT_STORAGE_DIR / "store.json"


def ensure_storage_dir() -> Path:
    """Ensures the storage directory exists with proper permissions."""
    DEFAULT_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    return DEFAULT_STORAGE_DIR


def save_store(documents: dict, chunks: list, store_file: Path = DEFAULT_STORE_FILE) -> None:
    """Serializes documents metadata and chunks to store.json."""
    ensure_storage_dir()
    data = {
        "version": "1.0",
        "documents": documents,
        "chunks": chunks
    }
    temp_file = store_file.with_suffix(".tmp")
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(temp_file, store_file)


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
