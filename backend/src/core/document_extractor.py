"""Document parser and text extractor supporting PDF, DOCX, TXT, MD, CSV, JSON."""

import os
import io
import json
import csv
import hashlib
from pathlib import Path
from typing import Dict, Any, Tuple
from pypdf import PdfReader
import docx


class DocumentExtractor:
    @staticmethod
    def calculate_file_hash(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    @classmethod
    def extract_text(cls, filename: str, content: bytes) -> Tuple[str, Dict[str, Any]]:
        """
        Extract text from raw file bytes.
        Returns: (extracted_text, metadata_dict)
        """
        ext = os.path.splitext(filename)[1].lower()
        sha256 = cls.calculate_file_hash(content)
        meta: Dict[str, Any] = {
            "filename": filename,
            "extension": ext,
            "sha256": sha256,
            "size_bytes": len(content),
            "is_scanned_pdf": False,
            "ocr_recommended": False
        }

        if ext in [".txt", ".md", ".log"]:
            try:
                text = content.decode("utf-8")
            except UnicodeDecodeError:
                text = content.decode("latin-1", errors="replace")
            meta["char_count"] = len(text)
            return text, meta

        elif ext == ".pdf":
            try:
                reader = PdfReader(io.BytesIO(content))
                pages_text = []
                for i, page in enumerate(reader.pages):
                    t = page.extract_text() or ""
                    pages_text.append(t)
                full_text = "\n\n".join(pages_text).strip()
                meta["page_count"] = len(reader.pages)
                meta["char_count"] = len(full_text)

                # Heuristic: if pages exist but average extracted characters per page is very low, mark scanned
                if len(reader.pages) > 0 and len(full_text) / len(reader.pages) < 40:
                    meta["is_scanned_pdf"] = True
                    meta["ocr_recommended"] = True
                    meta["warning"] = "Scanned PDF detected. Insufficient text extracted. OCR required."

                return full_text, meta
            except Exception as e:
                raise ValueError(f"Failed to parse PDF document: {str(e)}")

        elif ext == ".docx":
            try:
                doc = docx.Document(io.BytesIO(content))
                paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
                full_text = "\n".join(paragraphs)
                meta["paragraph_count"] = len(paragraphs)
                meta["char_count"] = len(full_text)
                return full_text, meta
            except Exception as e:
                raise ValueError(f"Failed to parse DOCX document: {str(e)}")

        elif ext == ".csv":
            try:
                text_stream = io.StringIO(content.decode("utf-8", errors="replace"))
                reader = csv.reader(text_stream)
                rows = list(reader)
                text = "\n".join([", ".join(r) for r in rows])
                meta["row_count"] = len(rows)
                meta["char_count"] = len(text)
                return text, meta
            except Exception as e:
                raise ValueError(f"Failed to parse CSV document: {str(e)}")

        elif ext == ".json":
            try:
                data = json.loads(content.decode("utf-8", errors="replace"))
                text = json.dumps(data, indent=2)
                meta["char_count"] = len(text)
                return text, meta
            except Exception as e:
                raise ValueError(f"Failed to parse JSON document: {str(e)}")

        else:
            raise ValueError(f"Unsupported document format: '{ext}'. Supported formats: .pdf, .docx, .txt, .md, .csv, .json")
