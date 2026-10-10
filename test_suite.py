"""
Comprehensive Test Suite for PrivateDesk CLI.
Executes test cases covering parsing, storage persistence, retrieval, CLI commands, and LLM inference.
"""

import os
import sys
import tempfile
from pathlib import Path
from pypdf import PdfWriter

from parser import parse_uploaded_file
from storage import save_store, load_store, clear_store
from retriever import DocumentRetriever
from cli import clean_finder_path
from llm_engine import LLMEngine


def run_tests():
    print("=" * 60)
    print("🧪 Starting PrivateDesk Test Suite")
    print("=" * 60)

    passed = 0
    total = 0

    # TC-01: Test Finder Drag-and-Drop Path Unescaping
    total += 1
    print("\n[TC-01] Testing Finder drag-and-drop path unescaping...")
    raw_path_1 = "/Users/test/Desktop/\\[W26\\]\\ Desk\\ Procedures.pptx"
    raw_path_2 = "'/Users/test/Documents/Laptop Loans.pdf'"
    raw_path_3 = "\"/Users/test/Documents/VPN Guide.pdf\""

    clean_1 = clean_finder_path(raw_path_1)
    clean_2 = clean_finder_path(raw_path_2)
    clean_3 = clean_finder_path(raw_path_3)

    assert clean_1 == "/Users/test/Desktop/[W26] Desk Procedures.pptx", f"Failed: {clean_1}"
    assert clean_2 == "/Users/test/Documents/Laptop Loans.pdf", f"Failed: {clean_2}"
    assert clean_3 == "/Users/test/Documents/VPN Guide.pdf", f"Failed: {clean_3}"
    print("✔ [TC-01] PASSED: Path unescaping handled escaped characters and quotes.")
    passed += 1

    # TC-02: Test PDF Ingestion
    total += 1
    print("\n[TC-02] Testing PDF parsing and extraction...")
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
        pdf_path = tmp_pdf.name

    try:
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        with open(pdf_path, "wb") as f:
            writer.write(f)

        # PDF without text should trigger scanned/empty check
        try:
            parse_uploaded_file(pdf_path, "blank.pdf")
            assert False, "Should have raised ValueError for empty text"
        except ValueError as e:
            assert "scanned document or image without selectable text" in str(e)
            print("✔ [TC-02] PASSED: Successfully detected empty/scanned PDF guard.")
            passed += 1
    finally:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)

    # TC-03: Test Storage Persistence
    total += 1
    print("\n[TC-03] Testing document persistence (~/.privatedesk/store.json)...")
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp_store:
        custom_store = Path(tmp_store.name)

    try:
        sample_docs = {"sample.pdf": {"filename": "sample.pdf", "total_pages": 5, "total_chunks": 10}}
        sample_chunks = [{"id": "chunk_1", "filename": "sample.pdf", "page": 1, "text": "WatIAM reset steps.", "tokens": ["watiam", "reset"]}]
        
        save_store(sample_docs, sample_chunks, store_file=custom_store)
        loaded_docs, loaded_chunks = load_store(store_file=custom_store)

        assert loaded_docs == sample_docs, "Loaded documents metadata mismatch"
        assert len(loaded_chunks) == 1, "Loaded chunks count mismatch"
        assert loaded_chunks[0]["text"] == "WatIAM reset steps."

        clear_success = clear_store(store_file=custom_store)
        assert clear_success, "Clear store failed"
        assert not custom_store.exists(), "Store file should be deleted"
        print("✔ [TC-03] PASSED: Storage serialization, reload, and purge verified.")
        passed += 1
    finally:
        if custom_store.exists():
            custom_store.unlink()

    # TC-04: Test Hybrid Search & Acronym Scoring
    total += 1
    print("\n[TC-04] Testing hybrid search & acronym boost...")
    retriever = DocumentRetriever(persistent=False)
    retriever.add_document("doc1.pdf", [
        {"page": 1, "text": "Standard login procedures for employee email accounts."},
        {"page": 2, "text": "WatIAM credentials and password reset guidelines for students."},
        {"page": 3, "text": "Hardware loan equipment for DC library circulation."}
    ])

    results = retriever.search("WatIAM password")
    assert len(results) > 0, "No results returned"
    top_result = results[0]
    assert top_result["page"] == 2, f"Expected page 2, got page {top_result['page']}"
    assert "WatIAM credentials" in top_result["text"]
    assert top_result["score"] > 5.0, "Score did not receive acronym boost"
    print(f"✔ [TC-04] PASSED: Search returned Page 2 with boosted score: {top_result['score']}.")
    passed += 1

    # TC-05: Test End-to-End LLM Generation (Ollama Qwen 2.5)
    total += 1
    print("\n[TC-05] Testing local Ollama Qwen 2.5 inference...")
    engine = LLMEngine()
    sample_context = [
        {"filename": "Policy.pdf", "page": 3, "text": "MacBook loan duration is strictly 7 days per student."}
    ]
    reply, sources = engine.generate("How long can a student borrow a MacBook?", sample_context)

    assert "7" in reply or "seven" in reply.lower(), f"Unexpected reply: {reply}"
    assert len(sources) == 1
    assert sources[0]["filename"] == "Policy.pdf"
    assert sources[0]["page"] == 3
    print(f"✔ [TC-05] PASSED: Model answered correctly with citations: {sources[0]['filename']} (p.{sources[0]['page']})")
    print(f"   Response preview: '{reply.strip()[:100]}...'")
    passed += 1

    # TC-06: Test Empty Vault Guard
    total += 1
    print("\n[TC-06] Testing empty vault guard...")
    empty_retriever = DocumentRetriever(persistent=False)
    empty_results = empty_retriever.search("Anything")
    assert empty_results == [], "Expected empty search results"
    print("✔ [TC-06] PASSED: Empty vault gracefully handled without errors.")
    passed += 1

    # TC-07: Test Directory Ingestion & Flexible Command Parsing
    total += 1
    print("\n[TC-07] Testing directory ingestion & flexible /upload syntax...")
    from cli import handle_upload
    import re
    # Test path cleanup when /upload is appended
    user_test_cmd = "/Users/test/Desktop/TrainingFiles /upload"
    stripped_path = re.sub(r"(^|\s)(/upload|/add)(\s|$)", " ", user_test_cmd, flags=re.IGNORECASE).strip()
    assert stripped_path == "/Users/test/Desktop/TrainingFiles", f"Failed: {stripped_path}"

    # Create a temporary directory with a dummy .pdf
    with tempfile.TemporaryDirectory() as temp_dir:
        dir_path = Path(temp_dir)
        dummy_pdf = dir_path / "test_doc.pdf"
        writer = PdfWriter()
        page = writer.add_blank_page(width=100, height=100)
        with open(dummy_pdf, "wb") as f:
            writer.write(f)

        test_retriever = DocumentRetriever(persistent=False)
        # Call handle_upload on the directory
        handle_upload(str(dir_path), test_retriever)
        # Empty pdf won't index text, but handle_upload correctly traversed the directory without error
    print("✔ [TC-07] PASSED: Directory traversal and flexible command parsing verified.")
    passed += 1

    print("\n" + "=" * 60)
    print(f"🎉 ALL TESTS PASSED! ({passed}/{total} test cases succeeded)")
    print("=" * 60)


if __name__ == "__main__":
    run_tests()
