import re
import unicodedata
from datetime import date, datetime
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_TEXT_CHARS = 30000
SUPPORTED = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".csv": "text/csv",
}


class FileError(Exception):
    pass


def clean_name(filename: str | None) -> tuple[str, str]:
    name = Path((filename or "").replace("\\", "/")).name.strip()
    name = "".join(char for char in name if char.isprintable())
    extension = Path(name).suffix.lower()
    if not name or extension not in SUPPORTED:
        raise FileError("Upload a PDF, TXT, MD, or CSV file.")
    return name[:160], extension


def extract_text(data: bytes, extension: str) -> str:
    if not data:
        raise FileError("The file is empty.")
    if len(data) > MAX_FILE_BYTES:
        raise FileError("Files must be 5 MB or smaller.")
    if extension == ".pdf":
        try:
            reader = PdfReader(BytesIO(data))
            if reader.is_encrypted:
                raise FileError("Encrypted PDFs are not supported.")
            if len(reader.pages) > 30:
                raise FileError("PDFs must have 30 pages or fewer.")
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except FileError:
            raise
        except Exception as exc:
            raise FileError("The PDF could not be read.") from exc
    else:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise FileError("Text files must use UTF-8 encoding.") from exc
    text = text.strip()
    if len(text) < 20:
        raise FileError("No readable text was found. Scanned PDFs need OCR before upload.")
    return text[:MAX_TEXT_CHARS]


def slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    result = re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")[:70].strip("-")
    return result or "document"


def relative_destination(category: str, title: str, document_date: date | None, extension: str) -> Path:
    year = str(document_date.year) if document_date else "Undated"
    prefix = f"{document_date.isoformat()}-" if document_date else ""
    return Path(year) / category / f"{prefix}{slug(title)}{extension}"


def next_available(archive_root: Path, relative: Path) -> Path:
    candidate = archive_root / relative
    count = 2
    while candidate.exists():
        candidate = archive_root / relative.parent / f"{relative.stem}-{count}{relative.suffix}"
        count += 1
    return candidate
