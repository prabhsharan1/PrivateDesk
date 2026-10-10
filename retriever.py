"""
Document Chunk Store & Hybrid Retriever for PrivateDesk CLI.
Slices document pages into chunks and performs fast, zero-dependency hybrid search
(exact keyword/acronym boost + term frequency similarity).
Supports persistent caching across terminal sessions via storage.py.
"""

import re
import math
from collections import Counter
from storage import save_store, load_store, clear_store


class DocumentRetriever:
    def __init__(self, chunk_size: int = 400, chunk_overlap: int = 50, persistent: bool = True):
        self.chunk_size = chunk_size        # in words
        self.chunk_overlap = chunk_overlap  # in words
        self.persistent = persistent
        self.chunks: list[dict] = []
        self.documents: dict[str, dict] = {} # filename -> metadata

        if self.persistent:
            self.load_from_disk()

    def load_from_disk(self):
        """Loads cached documents and chunks from persistent storage."""
        docs, raw_chunks = load_store()
        self.documents = docs
        self.chunks = []
        for c in raw_chunks:
            tokens = c.get("tokens", [])
            # Reconstruct Counter for fast lookup
            token_counts = Counter(tokens)
            self.chunks.append({
                "id": c.get("id"),
                "filename": c.get("filename"),
                "page": c.get("page"),
                "text": c.get("text", ""),
                "tokens": tokens,
                "token_counts": token_counts
            })

    def _sync_to_disk(self):
        """Persists current memory state to disk if persistence is enabled."""
        if not self.persistent:
            return
        # Serialize chunks cleanly without raw Counter objects
        serializable_chunks = []
        for c in self.chunks:
            serializable_chunks.append({
                "id": c["id"],
                "filename": c["filename"],
                "page": c["page"],
                "text": c["text"],
                "tokens": c["tokens"]
            })
        save_store(self.documents, serializable_chunks)

    def chunk_text(self, text: str) -> list[str]:
        """Splits text into chunks of specified word count with overlap."""
        words = text.split()
        if len(words) <= self.chunk_size:
            return [text]

        chunks = []
        start = 0
        while start < len(words):
            end = min(start + self.chunk_size, len(words))
            chunk_words = words[start:end]
            chunks.append(" ".join(chunk_words))
            if end == len(words):
                break
            start += self.chunk_size - self.chunk_overlap
        return chunks

    def add_document(self, filename: str, pages: list[dict]):
        """Indexes all pages from a parsed document."""
        # Remove previous version if re-uploaded
        self.remove_document(filename, sync=False)

        total_chunks = 0
        for page_data in pages:
            page_num = page_data["page"]
            text = page_data["text"]
            page_chunks = self.chunk_text(text)

            for chunk_idx, chunk_text in enumerate(page_chunks):
                chunk_id = f"{filename}_p{page_num}_c{chunk_idx}"
                tokens = self._tokenize(chunk_text)
                self.chunks.append({
                    "id": chunk_id,
                    "filename": filename,
                    "page": page_num,
                    "text": chunk_text,
                    "tokens": tokens,
                    "token_counts": Counter(tokens)
                })
                total_chunks += 1

        self.documents[filename] = {
            "filename": filename,
            "total_pages": len(pages),
            "total_chunks": total_chunks
        }
        self._sync_to_disk()

    def remove_document(self, filename: str, sync: bool = True):
        """Removes all chunks associated with a filename."""
        self.chunks = [c for c in self.chunks if c["filename"] != filename]
        if filename in self.documents:
            del self.documents[filename]
        if sync:
            self._sync_to_disk()

    def clear_all(self):
        """Purges all documents and chunks from memory and persistent disk store."""
        self.chunks.clear()
        self.documents.clear()
        if self.persistent:
            clear_store()

    def list_documents(self) -> list[dict]:
        """Returns summary of all loaded documents."""
        return list(self.documents.values())

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize text into lowercase words/alphanumerics, preserving acronyms."""
        return [t.lower() for t in re.findall(r"\b[\w\.\-]+\b", text)]

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        """
        Hybrid search across all indexed chunks.
        Combines exact acronym/phrase matching with TF-IDF keyword relevance.
        """
        if not self.chunks:
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        # Find raw terms for exact matching (e.g., "WatIAM", "eduroam")
        raw_query_words = [w.strip() for w in query.split() if len(w.strip()) > 1]

        scores = []
        for chunk in self.chunks:
            score = 0.0
            chunk_text = chunk["text"]
            chunk_tokens = chunk["tokens"]
            token_counts = chunk["token_counts"]

            if not chunk_tokens:
                continue

            # 1. Exact match / Acronym boost
            for word in raw_query_words:
                if word in chunk_text:
                    score += 5.0
                elif word.lower() in chunk_text.lower():
                    score += 2.0

            # 2. Term Frequency (TF)
            matched_terms = 0
            for qt in query_tokens:
                count = token_counts.get(qt, 0)
                if count > 0:
                    tf = count / len(chunk_tokens)
                    score += (tf * 10.0)
                    matched_terms += 1

            # Match ratio bonus
            if query_tokens:
                score *= (1.0 + (matched_terms / len(query_tokens)))

            if score > 0:
                scores.append((score, chunk))

        # Sort descending by score
        scores.sort(key=lambda x: x[0], reverse=True)

        results = []
        for score, chunk in scores[:top_k]:
            results.append({
                "filename": chunk["filename"],
                "page": chunk["page"],
                "text": chunk["text"],
                "score": round(score, 3)
            })

        return results
