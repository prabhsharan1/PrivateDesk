"""
Document Parser for PrivateDesk / IST Bot.
Extracts clean, structured text and Markdown from PDFs and PowerPoint presentations.
Optimized for local LLM inference (Qwen 2.5):
- Converts PDF and PPTX tables into clean Markdown tables.
- Preserves logical reading order, headings, and bullet points.
- Automatically repairs hyphenated line wraps and fragmented sentences.
- Primary engine: PyMuPDF (fast, layout & table aware).
- Resilient fallback: pypdf (pure Python layout extraction).
"""

import os
import re

# Primary engine: PyMuPDF (fast, detects tables and layout reading order)
try:
    import pymupdf
    if hasattr(pymupdf, "no_recommend_layout"):
        pymupdf.no_recommend_layout()
    HAS_PYMUPDF = True
except ImportError:
    pymupdf = None
    HAS_PYMUPDF = False

# Resilient fallback engine: pypdf
from pypdf import PdfReader
from pypdf.errors import PdfReadError, FileNotDecryptedError


def clean_markdown_for_llm(text: str) -> str:
    """
    Cleans raw extracted text into clean, structured Markdown suitable for Qwen:
    - Normalizes control characters and multiple newlines.
    - Rejoins hyphenated line breaks (e.g., 'connec-\ntion' -> 'connection').
    - Standardizes bullet characters (•, ·, etc.) into '- '.
    - Rejoins broken sentences while preserving Markdown tables, headers, and lists.
    """
    if not text:
        return ""

    # Normalize newlines and strip non-printable ASCII control chars
    text = text.replace("\x0c", "\n").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[\x00-\x08\x0b\x0e-\x1f\x7f]", "", text)

    # Rejoin hyphenated line breaks
    text = re.sub(r"(\w+)-\n(\w+)", r"\1\2", text)

    # Standardize bullet points
    text = re.sub(r"^[ \t]*[•·▪▸‣⁃]\s*", "- ", text, flags=re.MULTILINE)

    # Process line-by-line to join wrapped sentences within paragraphs
    lines = text.split("\n")
    formatted = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if formatted and formatted[-1] != "":
                formatted.append("")
            continue

        is_structural = (
            stripped.startswith(("|", "#", "-", "*", ">")) or
            bool(re.match(r"^\d+[\.\)]\s", stripped))
        )

        if formatted and formatted[-1] != "":
            prev = formatted[-1]
            prev_structural = (
                prev.startswith(("|", "#", "-", "*", ">")) or
                bool(re.match(r"^\d+[\.\)]\s", prev))
            )
            # Rejoin non-structural sentences that wrap across lines
            if not is_structural and not prev_structural and not prev.endswith((".", "!", "?", ":", ";")):
                formatted[-1] = prev + " " + stripped
                continue

        formatted.append(stripped)

    result = "\n".join(formatted).strip()
    return re.sub(r"\n{3,}", "\n\n", result)


class DocumentParser:
    @staticmethod
    def _parse_pdf_with_pymupdf(file_path: str, filename: str) -> list[dict]:
        """Extracts text and markdown tables from PDF using PyMuPDF."""
        doc = pymupdf.open(file_path)
        try:
            if doc.is_encrypted:
                auth = doc.authenticate("")
                if not auth:
                    raise ValueError(f"'{filename}' is password-protected. Please remove the password and retry.")

            total_pages = len(doc)
            total_text_length = 0
            pages_content = []

            for idx, page in enumerate(doc, start=1):
                page_items = []
                used_tables = set()

                # 1. Detect tables on the page
                try:
                    tabs = page.find_tables()
                    tab_list = tabs.tables if tabs else []
                except Exception:
                    tab_list = []

                def block_overlaps_table(b_bbox, t_bbox):
                    bx0, by0, bx1, by1 = b_bbox
                    tx0, ty0, tx1, ty1 = t_bbox
                    cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
                    return tx0 <= cx <= tx1 and ty0 <= cy <= ty1

                # 2. Extract text blocks in reading order
                try:
                    blocks = page.get_text("blocks")
                except Exception:
                    blocks = []

                for b in blocks:
                    bbox = b[:4]
                    b_text = b[4].strip()
                    if not b_text:
                        continue

                    # Check if block is inside a table
                    in_table = False
                    for t_idx, t in enumerate(tab_list):
                        if block_overlaps_table(bbox, t.bbox):
                            in_table = True
                            if t_idx not in used_tables:
                                used_tables.add(t_idx)
                                md_table = t.to_markdown().strip()
                                if md_table:
                                    page_items.append((t.bbox[1], md_table))
                            break

                    if not in_table:
                        page_items.append((bbox[1], b_text))

                # Insert any tables that did not intersect with text blocks
                for t_idx, t in enumerate(tab_list):
                    if t_idx not in used_tables:
                        md_table = t.to_markdown().strip()
                        if md_table:
                            page_items.append((t.bbox[1], md_table))

                # Sort all content vertically (Y-coordinate reading order)
                page_items.sort(key=lambda x: x[0])
                raw_page_text = "\n\n".join(content for _, content in page_items)

                # Clean into structured markdown for Qwen
                cleaned = clean_markdown_for_llm(raw_page_text)
                if cleaned:
                    total_text_length += len(cleaned)
                    pages_content.append({
                        "filename": filename,
                        "page": idx,
                        "text": cleaned
                    })

            if total_pages > 0 and total_text_length < 50:
                raise ValueError(
                    f"'{filename}' appears to be a scanned document or image without selectable text. "
                    "Please upload a digital or OCR-enabled PDF."
                )

            return pages_content
        finally:
            doc.close()

    @staticmethod
    def _parse_pdf_with_pypdf(file_path: str, filename: str) -> list[dict]:
        """Resilient pure-Python fallback using pypdf."""
        reader = PdfReader(file_path)
        if reader.is_encrypted:
            try:
                decrypted = reader.decrypt("")
                if not decrypted:
                    raise ValueError(f"'{filename}' is password-protected. Please remove the password and retry.")
            except Exception:
                raise ValueError(f"'{filename}' is password-protected. Please remove the password and retry.")

        total_pages = len(reader.pages)
        total_text_length = 0
        pages_content = []

        for idx, page in enumerate(reader.pages, start=1):
            raw_text = ""
            try:
                raw_text = page.extract_text(extraction_mode="layout") or ""
            except Exception:
                try:
                    raw_text = page.extract_text() or ""
                except Exception:
                    raw_text = ""

            cleaned = clean_markdown_for_llm(raw_text)
            if cleaned:
                total_text_length += len(cleaned)
                pages_content.append({
                    "filename": filename,
                    "page": idx,
                    "text": cleaned
                })

        if total_pages > 0 and total_text_length < 50:
            raise ValueError(
                f"'{filename}' appears to be a scanned document or image without selectable text. "
                "Please upload a digital or OCR-enabled PDF."
            )

        return pages_content

    @classmethod
    def parse_pdf(cls, file_path: str, filename: str) -> list[dict]:
        """
        Extracts structured text and Markdown from a PDF file page-by-page.
        Uses PyMuPDF if available for table detection and layout preservation,
        with seamless fallback to pypdf layout mode.
        """
        if HAS_PYMUPDF:
            try:
                return cls._parse_pdf_with_pymupdf(file_path, filename)
            except ValueError:
                # Password errors or scanned document errors should be raised directly
                raise
            except Exception:
                # If pymupdf encounters unexpected low-level corruption, try pypdf fallback
                pass

        try:
            return cls._parse_pdf_with_pypdf(file_path, filename)
        except (FileNotDecryptedError, ValueError):
            raise
        except PdfReadError as e:
            raise ValueError(f"Failed to read PDF '{filename}': {str(e)}")
        except Exception as e:
            raise ValueError(f"Error parsing '{filename}': {str(e)}")

    @staticmethod
    def parse_pptx(file_path: str, filename: str) -> list[dict]:
        """
        Extracts text from a PowerPoint (.pptx) presentation slide by slide.
        Extracts slide headings, bullet points, shape text, PowerPoint tables (as Markdown),
        and speaker notes.
        Returns a list of dicts:
        [{"filename": filename, "page": slide_number, "text": "Slide text..."}]
        """
        try:
            from pptx import Presentation
        except ImportError:
            raise ValueError("python-pptx is required to parse PowerPoint files. Run: pip install python-pptx")

        slides_content = []
        try:
            prs = Presentation(file_path)
            for slide_num, slide in enumerate(prs.slides, start=1):
                slide_text = []

                # Extract text and tables from slide shapes
                for shape in slide.shapes:
                    if shape.has_table:
                        rows_data = []
                        for row in shape.table.rows:
                            rows_data.append([cell.text.strip().replace("\n", " ") for cell in row.cells])
                        if rows_data:
                            header = "| " + " | ".join(rows_data[0]) + " |"
                            sep = "| " + " | ".join(["---"] * len(rows_data[0])) + " |"
                            body_rows = ["| " + " | ".join(r) + " |" for r in rows_data[1:]]
                            md_table = "\n".join([header, sep] + body_rows)
                            slide_text.append(md_table)
                    elif hasattr(shape, "text") and shape.text.strip():
                        slide_text.append(shape.text.strip())

                # Extract speaker notes if available
                if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
                    notes = slide.notes_slide.notes_text_frame.text.strip()
                    if notes:
                        slide_text.append(f"[Speaker Notes: {notes}]")

                cleaned_text = clean_markdown_for_llm("\n\n".join(slide_text))
                if cleaned_text:
                    slides_content.append({
                        "filename": filename,
                        "page": slide_num,
                        "text": cleaned_text
                    })

            if not slides_content:
                raise ValueError(f"'{filename}' contains no readable text across its slides.")

            return slides_content

        except Exception as e:
            if isinstance(e, ValueError):
                raise
            raise ValueError(f"Error reading PowerPoint '{filename}': {str(e)}")


def parse_uploaded_file(file_path: str, filename: str) -> list[dict]:
    """Factory function to parse uploaded documents based on extension (.pdf or .pptx)."""
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".pdf":
        return DocumentParser.parse_pdf(file_path, filename)
    elif ext == ".pptx":
        return DocumentParser.parse_pptx(file_path, filename)
    else:
        raise ValueError(f"Unsupported file format '{ext}'. Supported formats: .pdf, .pptx")

