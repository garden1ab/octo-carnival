"""
document_handler.py — File upload ingestion, text extraction, and chunking.

Supported formats
-----------------
  .txt  .md   → plain text read
  .pdf        → pdfminer.six
  .docx       → python-docx
  .csv        → csv stdlib
  .html .htm  → BeautifulSoup4
  (anything else) → attempted UTF-8 decode, error logged gracefully
"""

from __future__ import annotations

import csv
import io
import logging
import mimetypes
import os
import uuid
from pathlib import Path
from typing import IO

from schemas import DocumentChunk

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional import guards — libraries may not be installed in all envs
# ---------------------------------------------------------------------------

try:
    from pdfminer.high_level import extract_text as pdf_extract_text
    _PDF_AVAILABLE = True
except ImportError:
    _PDF_AVAILABLE = False
    logger.warning("pdfminer.six not available — PDF parsing disabled")

try:
    from docx import Document as DocxDocument
    _DOCX_AVAILABLE = True
except ImportError:
    _DOCX_AVAILABLE = False
    logger.warning("python-docx not available — DOCX parsing disabled")

try:
    from bs4 import BeautifulSoup
    _BS4_AVAILABLE = True
except ImportError:
    _BS4_AVAILABLE = False
    logger.warning("beautifulsoup4 not available — HTML parsing will use raw text")


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

class DocumentHandler:
    """
    Accepts raw file bytes, extracts text, and splits it into manageable chunks
    that can be forwarded to worker agents.
    """

    def __init__(self, chunk_size: int = 3000, chunk_overlap: int = 200,
                 upload_dir: str = "./uploads"):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def process(self, filename: str, data: bytes) -> list[DocumentChunk]:
        """
        Save file to disk, extract text, and return a list of DocumentChunks.
        """
        safe_name = f"{uuid.uuid4().hex}_{Path(filename).name}"
        dest = self.upload_dir / safe_name
        dest.write_bytes(data)
        logger.info("Saved upload → %s (%d bytes)", dest, len(data))

        mime_type = self._detect_mime(filename, data)
        text = self._extract_text(dest, mime_type)

        if not text.strip():
            logger.warning("No text extracted from %s", filename)
            text = "[Document could not be parsed — no extractable text found]"

        chunks = self._chunk(text)
        logger.info("Document '%s' → %d chunk(s)", filename, len(chunks))

        return [
            DocumentChunk(
                filename=filename,
                mime_type=mime_type,
                chunk_index=i,
                total_chunks=len(chunks),
                text=chunk,
            )
            for i, chunk in enumerate(chunks)
        ]

    # ------------------------------------------------------------------
    # MIME detection
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_mime(filename: str, data: bytes) -> str:
        mime, _ = mimetypes.guess_type(filename)
        if mime:
            return mime
        # Sniff first bytes
        if data[:4] == b"%PDF":
            return "application/pdf"
        if data[:2] in (b"PK",):
            return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        return "text/plain"

    # ------------------------------------------------------------------
    # Text extraction dispatch
    # ------------------------------------------------------------------

    def _extract_text(self, path: Path, mime_type: str) -> str:
        suffix = path.suffix.lower()

        if mime_type == "application/pdf" or suffix == ".pdf":
            return self._from_pdf(path)

        if (mime_type == "application/vnd.openxmlformats-officedocument"
                         ".wordprocessingml.document" or suffix == ".docx"):
            return self._from_docx(path)

        if mime_type in ("text/html", "application/xhtml+xml") or suffix in (".html", ".htm"):
            return self._from_html(path)

        if mime_type == "text/csv" or suffix == ".csv":
            return self._from_csv(path)

        # Fallback: plain text / markdown / code
        return self._from_text(path)

    # ------------------------------------------------------------------
    # Format-specific extractors
    # ------------------------------------------------------------------

    @staticmethod
    def _from_pdf(path: Path) -> str:
        if not _PDF_AVAILABLE:
            return "[PDF parsing unavailable — install pdfminer.six]"
        try:
            return pdf_extract_text(str(path)) or ""
        except Exception as exc:
            logger.error("PDF extraction failed for %s: %s", path, exc)
            return f"[PDF extraction error: {exc}]"

    @staticmethod
    def _from_docx(path: Path) -> str:
        if not _DOCX_AVAILABLE:
            return "[DOCX parsing unavailable — install python-docx]"
        try:
            doc = DocxDocument(str(path))
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except Exception as exc:
            logger.error("DOCX extraction failed for %s: %s", path, exc)
            return f"[DOCX extraction error: {exc}]"

    @staticmethod
    def _from_html(path: Path) -> str:
        raw = path.read_bytes()
        if _BS4_AVAILABLE:
            try:
                soup = BeautifulSoup(raw, "html.parser")
                return soup.get_text(separator="\n", strip=True)
            except Exception as exc:
                logger.error("HTML parsing failed: %s", exc)
        return raw.decode("utf-8", errors="replace")

    @staticmethod
    def _from_csv(path: Path) -> str:
        try:
            with path.open(newline="", encoding="utf-8", errors="replace") as fh:
                reader = csv.reader(fh)
                rows = [", ".join(row) for row in reader]
            return "\n".join(rows)
        except Exception as exc:
            logger.error("CSV extraction failed: %s", exc)
            return f"[CSV extraction error: {exc}]"

    @staticmethod
    def _from_text(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            logger.error("Text read failed for %s: %s", path, exc)
            return f"[Text read error: {exc}]"

    # ------------------------------------------------------------------
    # Chunking
    # ------------------------------------------------------------------

    def _chunk(self, text: str) -> list[str]:
        """
        Splits text into overlapping windows of `chunk_size` characters.
        Tries to break on sentence/paragraph boundaries.
        """
        if len(text) <= self.chunk_size:
            return [text]

        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            # Walk back to find a good break point (newline or period)
            if end < len(text):
                for sep in ("\n\n", "\n", ". ", " "):
                    idx = text.rfind(sep, start, end)
                    if idx != -1 and idx > start:
                        end = idx + len(sep)
                        break
            chunks.append(text[start:end])
            start = end - self.chunk_overlap  # slide with overlap
            if start < 0:
                start = 0
        return chunks
