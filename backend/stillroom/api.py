import csv
from io import StringIO
from urllib.parse import urlsplit

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from .ai import AIError, classify
from .config import ROOT, Settings, get_settings
from .files import MAX_FILE_BYTES, FileError, clean_name, extract_text
from .models import Document, Event, ProposalUpdate, Stats
from .store import (approve_document, archive_document, create_document, edit_proposal,
                    file_path, get_document, list_documents, list_events, save_proposal,
                    stats, undo_archive)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="Stillroom API", version="0.1.0")

    @app.middleware("http")
    async def protect_local_writes(request: Request, call_next):
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("origin")
            if origin and urlsplit(origin).netloc != request.url.netloc:
                return Response("Cross-origin writes are not allowed", status_code=403)
            length = request.headers.get("content-length")
            if length:
                try:
                    if int(length) > MAX_FILE_BYTES + 64 * 1024:
                        return Response("Request is too large", status_code=413)
                except ValueError:
                    return Response("Invalid content length", status_code=400)
        return await call_next(request)

    def require_document(document_id: str) -> Document:
        document = get_document(settings.data_dir, document_id)
        if document is None:
            raise HTTPException(404, "File not found")
        return document

    @app.get("/api/health")
    def health():
        return {"status": "ok", "groq_configured": bool(settings.groq_api_key)}

    @app.get("/api/stats", response_model=Stats)
    def get_stats():
        return stats(settings.data_dir)

    @app.get("/api/documents", response_model=list[Document])
    def documents():
        return list_documents(settings.data_dir)

    @app.post("/api/documents", response_model=Document, status_code=201)
    async def upload_document(file: UploadFile = File(...)):
        try:
            name, extension = clean_name(file.filename)
            data = await file.read(MAX_FILE_BYTES + 1)
            text = extract_text(data, extension)
            return create_document(settings.data_dir, name, extension, data, text)
        except FileError as exc:
            raise HTTPException(422, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        finally:
            await file.close()

    @app.get("/api/documents/{document_id}", response_model=Document)
    def read_document(document_id: str):
        return require_document(document_id)

    @app.get("/api/documents/{document_id}/file")
    def download_document(document_id: str):
        document = require_document(document_id)
        path = file_path(settings.data_dir, document)
        if not path.is_file():
            raise HTTPException(409, "The stored file is missing")
        return FileResponse(path, media_type=document.media_type, filename=document.original_name)

    @app.post("/api/documents/{document_id}/analyze", response_model=Document)
    async def analyze_document(document_id: str):
        document = require_document(document_id)
        if document.state != "inbox":
            raise HTTPException(409, "Only inbox files can be analyzed")
        try:
            proposal = await classify(document, settings.groq_api_key, settings.groq_model)
            return save_proposal(settings.data_dir, document_id, proposal)
        except AIError as exc:
            raise HTTPException(502, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.put("/api/documents/{document_id}/proposal", response_model=Document)
    def update_proposal(document_id: str, update: ProposalUpdate):
        require_document(document_id)
        try:
            return edit_proposal(settings.data_dir, document_id, update)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/api/documents/{document_id}/approve", response_model=Document)
    def approve(document_id: str):
        require_document(document_id)
        try:
            return approve_document(settings.data_dir, document_id)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/api/documents/{document_id}/archive", response_model=Document)
    def archive(document_id: str):
        require_document(document_id)
        try:
            return archive_document(settings.data_dir, document_id)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/api/documents/{document_id}/undo", response_model=Document)
    def undo(document_id: str):
        require_document(document_id)
        try:
            return undo_archive(settings.data_dir, document_id)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get("/api/events", response_model=list[Event])
    def events():
        return list_events(settings.data_dir)

    @app.get("/api/manifest.csv")
    def manifest():
        def safe_cell(value):
            text = "" if value is None else str(value)
            return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text

        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["id", "original_name", "title", "category", "document_date",
                         "archived_path", "sha256", "archived_at"])
        for document in list_documents(settings.data_dir):
            if document.state == "archived":
                writer.writerow([safe_cell(value) for value in (
                    document.id, document.original_name, document.title,
                    document.category, document.document_date,
                    document.archived_path, document.sha256,
                    document.archived_at,
                )])
        return Response(output.getvalue(), media_type="text/csv", headers={
            "Content-Disposition": 'attachment; filename="stillroom-manifest.csv"',
        })

    dist = ROOT / "frontend" / "dist"
    if dist.is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def frontend(path: str):
            candidate = (dist / path).resolve()
            if candidate.is_file() and candidate.is_relative_to(dist.resolve()):
                return FileResponse(candidate)
            return FileResponse(dist / "index.html")

    return app


app = create_app()
