import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .files import SUPPORTED, next_available, relative_destination
from .models import Document, Event, Proposal, ProposalUpdate, Stats


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(data_dir: Path) -> sqlite3.Connection:
    data_dir.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(data_dir / "stillroom.db", timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout=15000")
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS documents (
        id TEXT PRIMARY KEY, original_name TEXT NOT NULL, extension TEXT NOT NULL,
        media_type TEXT NOT NULL, size_bytes INTEGER NOT NULL, sha256 TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL, state TEXT NOT NULL, extracted_text TEXT NOT NULL,
        category TEXT, title TEXT, summary TEXT, document_date TEXT, date_quote TEXT,
        evidence_quote TEXT, tags_json TEXT NOT NULL DEFAULT '[]', reviewed_at TEXT,
        archived_path TEXT, archived_at TEXT, user_edited INTEGER NOT NULL DEFAULT 0
    )""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_document_state_created ON documents(state, created_at)")
    db.execute("""CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT, document_id TEXT NOT NULL,
        action TEXT NOT NULL, path TEXT, at TEXT NOT NULL
    )""")
    return db


@contextmanager
def database(data_dir: Path):
    db = connect(data_dir)
    try:
        with db:
            yield db
    finally:
        db.close()


def _document(row: sqlite3.Row) -> Document:
    data = dict(row)
    data["tags"] = json.loads(data.pop("tags_json"))
    return Document.model_validate(data)


def present(document: Document, data_dir: Path) -> Document:
    if document.state == "ready" and document.category and document.title:
        relative = relative_destination(document.category, document.title,
                                        document.document_date, document.extension)
        candidate = next_available(data_dir / "archive", relative)
        return document.model_copy(update={"suggested_path": str(candidate.relative_to(data_dir / "archive"))})
    if document.state == "archived":
        return document.model_copy(update={"suggested_path": document.archived_path})
    return document


def list_documents(data_dir: Path) -> list[Document]:
    with database(data_dir) as db:
        rows = db.execute("SELECT * FROM documents ORDER BY created_at DESC").fetchall()
    return [present(_document(row), data_dir) for row in rows]


def get_document(data_dir: Path, document_id: str) -> Document | None:
    with database(data_dir) as db:
        row = db.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
    return present(_document(row), data_dir) if row else None


def create_document(data_dir: Path, name: str, extension: str, data: bytes, text: str) -> Document:
    document_id = str(uuid4())
    digest = hashlib.sha256(data).hexdigest()
    inbox = data_dir / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    path = inbox / f"{document_id}{extension}"
    try:
        with database(data_dir) as db:
            if db.execute("SELECT 1 FROM documents WHERE sha256 = ?", (digest,)).fetchone():
                raise ValueError("This exact file is already in Stillroom.")
            path.write_bytes(data)
            try:
                db.execute("""INSERT INTO documents
                    (id, original_name, extension, media_type, size_bytes, sha256, created_at,
                     state, extracted_text) VALUES (?, ?, ?, ?, ?, ?, ?, 'inbox', ?)""",
                    (document_id, name, extension, SUPPORTED[extension], len(data), digest, now(), text))
                db.execute("INSERT INTO events (document_id, action, at) VALUES (?, 'uploaded', ?)",
                           (document_id, now()))
            except Exception:
                path.unlink(missing_ok=True)
                raise
    except sqlite3.IntegrityError as exc:
        raise ValueError("This exact file is already in Stillroom.") from exc
    result = get_document(data_dir, document_id)
    assert result is not None
    return result


def save_proposal(data_dir: Path, document_id: str, proposal: Proposal) -> Document:
    with database(data_dir) as db:
        row = db.execute("SELECT state FROM documents WHERE id = ?", (document_id,)).fetchone()
        if row is None or row["state"] != "inbox":
            raise ValueError("Only inbox files can be analyzed.")
        db.execute("""UPDATE documents SET state = 'ready', category = ?, title = ?, summary = ?,
            document_date = ?, date_quote = ?, evidence_quote = ?, tags_json = ?, reviewed_at = NULL
            WHERE id = ?""",
            (proposal.category, proposal.title, proposal.summary,
             proposal.document_date.isoformat() if proposal.document_date else None,
             proposal.date_quote, proposal.evidence_quote, json.dumps(proposal.tags), document_id))
        db.execute("INSERT INTO events (document_id, action, at) VALUES (?, 'analyzed', ?)",
                   (document_id, now()))
    result = get_document(data_dir, document_id)
    assert result is not None
    return result


def edit_proposal(data_dir: Path, document_id: str, update: ProposalUpdate) -> Document:
    with database(data_dir) as db:
        row = db.execute("SELECT state, document_date, date_quote FROM documents WHERE id = ?",
                         (document_id,)).fetchone()
        if row is None or row["state"] != "ready":
            raise ValueError("Only ready files can be edited.")
        new_date = update.document_date.isoformat() if update.document_date else None
        date_quote = row["date_quote"] if new_date == row["document_date"] else ""
        db.execute("""UPDATE documents SET category = ?, title = ?, document_date = ?,
            date_quote = ?, tags_json = ?, reviewed_at = NULL, user_edited = 1 WHERE id = ?""",
            (update.category, update.title, new_date, date_quote, json.dumps(update.tags), document_id))
        db.execute("INSERT INTO events (document_id, action, at) VALUES (?, 'edited', ?)",
                   (document_id, now()))
    result = get_document(data_dir, document_id)
    assert result is not None
    return result


def approve_document(data_dir: Path, document_id: str) -> Document:
    with database(data_dir) as db:
        row = db.execute("SELECT state FROM documents WHERE id = ?", (document_id,)).fetchone()
        if row is None or row["state"] != "ready":
            raise ValueError("Only ready files can be approved.")
        db.execute("UPDATE documents SET reviewed_at = ? WHERE id = ?", (now(), document_id))
        db.execute("INSERT INTO events (document_id, action, at) VALUES (?, 'approved', ?)",
                   (document_id, now()))
    result = get_document(data_dir, document_id)
    assert result is not None
    return result


def _inbox_path(data_dir: Path, document: Document) -> Path:
    return data_dir / "inbox" / f"{document.id}{document.extension}"


def _archive_path(data_dir: Path, relative: str) -> Path:
    root = (data_dir / "archive").resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Invalid archive path")
    return path


def file_path(data_dir: Path, document: Document) -> Path:
    if document.state == "archived" and document.archived_path:
        return _archive_path(data_dir, document.archived_path)
    return _inbox_path(data_dir, document)


def _move_without_overwrite(source: Path, target: Path) -> None:
    try:
        os.link(source, target)
    except FileExistsError as exc:
        raise ValueError("The destination is occupied; nothing was moved.") from exc
    try:
        source.unlink()
    except Exception:
        target.unlink(missing_ok=True)
        raise


def archive_document(data_dir: Path, document_id: str) -> Document:
    db = connect(data_dir)
    source = target = None
    moved = False
    try:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
        if row is None:
            raise ValueError("File not found.")
        document = _document(row)
        if document.state != "ready" or document.reviewed_at is None:
            raise ValueError("Review and approve this file before archiving.")
        source = _inbox_path(data_dir, document)
        if not source.is_file():
            raise ValueError("The staged file is missing; nothing was moved.")
        relative = relative_destination(document.category, document.title,
                                        document.document_date, document.extension)
        target = next_available(data_dir / "archive", relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        _move_without_overwrite(source, target)
        moved = True
        archive_name = str(target.relative_to(data_dir / "archive"))
        db.execute("""UPDATE documents SET state = 'archived', archived_path = ?, archived_at = ?
            WHERE id = ?""", (archive_name, now(), document_id))
        db.execute("INSERT INTO events (document_id, action, path, at) VALUES (?, 'archived', ?, ?)",
                   (document_id, archive_name, now()))
        db.commit()
    except Exception:
        db.rollback()
        if moved and target and source and target.exists():
            _move_without_overwrite(target, source)
        raise
    finally:
        db.close()
    result = get_document(data_dir, document_id)
    assert result is not None
    return result


def undo_archive(data_dir: Path, document_id: str) -> Document:
    db = connect(data_dir)
    source = target = None
    moved = False
    try:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
        if row is None:
            raise ValueError("File not found.")
        document = _document(row)
        if document.state != "archived" or not document.archived_path:
            raise ValueError("Only archived files can be undone.")
        source = _archive_path(data_dir, document.archived_path)
        target = _inbox_path(data_dir, document)
        if not source.is_file() or target.exists():
            raise ValueError("The file is missing or its inbox location is occupied.")
        target.parent.mkdir(parents=True, exist_ok=True)
        _move_without_overwrite(source, target)
        moved = True
        db.execute("""UPDATE documents SET state = 'ready', archived_path = NULL,
            archived_at = NULL, reviewed_at = NULL WHERE id = ?""", (document_id,))
        db.execute("INSERT INTO events (document_id, action, path, at) VALUES (?, 'undone', ?, ?)",
                   (document_id, document.archived_path, now()))
        db.commit()
    except Exception:
        db.rollback()
        if moved and source and target and target.exists():
            _move_without_overwrite(target, source)
        raise
    finally:
        db.close()
    result = get_document(data_dir, document_id)
    assert result is not None
    return result


def list_events(data_dir: Path) -> list[Event]:
    with database(data_dir) as db:
        rows = db.execute("SELECT * FROM events ORDER BY id DESC LIMIT 100").fetchall()
    return [Event.model_validate(dict(row)) for row in rows]


def stats(data_dir: Path) -> Stats:
    with database(data_dir) as db:
        rows = db.execute("SELECT state, COUNT(*) AS n FROM documents GROUP BY state").fetchall()
        approved = db.execute("SELECT COUNT(*) FROM documents WHERE state = 'ready' AND reviewed_at IS NOT NULL").fetchone()[0]
    counts = {row["state"]: row["n"] for row in rows}
    return Stats(total=sum(counts.values()), inbox=counts.get("inbox", 0),
                 ready=counts.get("ready", 0), approved=approved,
                 archived=counts.get("archived", 0))
