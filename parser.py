"""
Document Parser for PrivateDesk / IST Bot.
Extracts clean, structured text from PDFs page-by-page.
Handles edge cases: encrypted PDFs, scanned PDFs, and malformed files.
"""

import os
from pypdf import PdfReader
from pypdf.errors import PdfReadError, FileNotDecryptedError


class DocumentParser:
    @staticmethod
    def parse_pdf(file_path: str, filename: str) -> list[dict]:
        """
        Extracts text from a PDF file page by page.
        Returns a list of dicts:
        [{"filename": filename, "page": 1, "text": "Page content..."}]
        """
        pages_content = []
        
        try:
            reader = PdfReader(file_path)
            
            # Check if encrypted / password protected
            if reader.is_encrypted:
                try:
                    # Attempt empty password decryption
                    decrypted = reader.decrypt("")
                    if not decrypted:
                        raise ValueError(f"'{filename}' is password-protected. Please remove the password and retry.")
                except Exception:
                    raise ValueError(f"'{filename}' is password-protected. Please remove the password and retry.")
            
            total_pages = len(reader.pages)
            total_text_length = 0

            for idx, page in enumerate(reader.pages, start=1):
                try:
                    raw_text = page.extract_text() or ""
                except Exception:
                    raw_text = ""
                
                # Normalize whitespace
                cleaned_text = "\n".join(
                    line.strip() for line in raw_text.splitlines() if line.strip()
                )
                
                if cleaned_text:
                    total_text_length += len(cleaned_text)
                    pages_content.append({
                        "filename": filename,
                        "page": idx,
                        "text": cleaned_text
                    })

            # Check if the document appears to be scanned images without text
            if total_pages > 0 and total_text_length < 50:
                raise ValueError(
                    f"'{filename}' appears to be a scanned document or image without selectable text. "
                    "Please upload a digital or OCR-enabled PDF."
                )

            return pages_content

        except FileNotDecryptedError:
            raise ValueError(f"'{filename}' is encrypted/password-protected.")
        except PdfReadError as e:
            raise ValueError(f"Failed to read PDF '{filename}': {str(e)}")
        except Exception as e:
            if isinstance(e, ValueError):
                raise
            raise ValueError(f"Error parsing '{filename}': {str(e)}")

    @staticmethod
    def parse_pptx(file_path: str, filename: str) -> list[dict]:
        """
        Extracts text from a PowerPoint (.pptx) presentation slide by slide.
        Extracts slide headings, bullet points, shape text, and speaker notes.
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

                # Extract text from slide shapes
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        slide_text.append(shape.text.strip())

                # Extract speaker notes if available
                if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
                    notes = slide.notes_slide.notes_text_frame.text.strip()
                    if notes:
                        slide_text.append(f"[Speaker Notes: {notes}]")

                cleaned_text = "\n".join(slide_text)
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

