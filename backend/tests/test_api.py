import csv
from datetime import date
from io import StringIO

import httpx
import pytest

import stillroom.api as api_module
from stillroom.api import create_app
from stillroom.config import Settings
from stillroom.models import Proposal


@pytest.fixture
def app(tmp_path):
    return create_app(Settings(tmp_path / "data", "test-key"))


async def upload(client: httpx.AsyncClient, filename: str, content: bytes) -> dict:
    response = await client.post("/api/documents", files={"file": (filename, content, "text/plain")})
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_review_archive_undo_and_manifest(app, monkeypatch):
    async def fake_classify(document, api_key, model):
        return Proposal(category="Projects", title="Fall planting plan",
                        summary="Notes for the fall planting day.",
                        document_date=date(2026, 10, 22), date_quote="October 22, 2026",
                        evidence_quote="fall planting day", tags=["garden"])

    monkeypatch.setattr(api_module, "classify", fake_classify)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        first = await upload(client, "../../garden.txt", b"Notes October 22, 2026: fall planting day for the community.")
        second = await upload(client, "garden-2.txt", b"Meeting October 22, 2026: fall planting day with volunteers.")
        duplicate = await client.post("/api/documents", files={"file": ("copy.txt", b"Notes October 22, 2026: fall planting day for the community.")})
        assert duplicate.status_code == 409
        first_id, second_id = first["id"], second["id"]
        assert (await client.post(f"/api/documents/{first_id}/archive")).status_code == 409
        analyzed = await client.post(f"/api/documents/{first_id}/analyze")
        assert analyzed.status_code == 200
        assert analyzed.json()["suggested_path"] == "2026/Projects/2026-10-22-fall-planting-plan.txt"
        assert (await client.post(f"/api/documents/{first_id}/archive")).status_code == 409
        edited = await client.put(f"/api/documents/{first_id}/proposal", json={
            "category": "Projects", "title": "Fall planting plan", "document_date": "2026-10-23", "tags": ["garden"],
        })
        assert edited.json()["date_quote"] == ""
        assert edited.json()["user_edited"] is True
        assert (await client.post(f"/api/documents/{first_id}/approve")).status_code == 200
        archived = await client.post(f"/api/documents/{first_id}/archive")
        assert archived.status_code == 200
        assert archived.json()["archived_path"].startswith("2026/Projects/2026-10-23")
        assert (await client.get(f"/api/documents/{first_id}/file")).content.startswith(b"Notes")
        assert "garden.txt" in (await client.get("/api/manifest.csv")).text
        undone = await client.post(f"/api/documents/{first_id}/undo")
        assert undone.json()["state"] == "ready"
        assert undone.json()["reviewed_at"] is None
        assert (await client.get("/api/stats")).json()["archived"] == 0
        assert len((await client.get("/api/events")).json()) >= 6
        assert (await client.get(f"/api/documents/{second_id}")).status_code == 200


@pytest.mark.asyncio
async def test_collisions_do_not_overwrite(app, monkeypatch):
    async def fake_classify(document, api_key, model):
        return Proposal(category="Projects", title="Same title", summary="A same titled document.",
                        document_date=None, date_quote="", evidence_quote="Project status", tags=[])

    monkeypatch.setattr(api_module, "classify", fake_classify)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        a = await upload(client, "one.md", b"Project status for October: first document.")
        b = await upload(client, "two.md", b"Project status for November: second document.")
        paths = []
        for item in (a, b):
            doc_id = item["id"]
            assert (await client.post(f"/api/documents/{doc_id}/analyze")).status_code == 200
            assert (await client.post(f"/api/documents/{doc_id}/approve")).status_code == 200
            paths.append((await client.post(f"/api/documents/{doc_id}/archive")).json()["archived_path"])
        assert paths == ["Undated/Projects/same-title.md", "Undated/Projects/same-title-2.md"]
        assert (await client.get(f"/api/documents/{a['id']}/file")).content != (await client.get(f"/api/documents/{b['id']}/file")).content


@pytest.mark.asyncio
async def test_rejects_invalid_file_and_serves_frontend(tmp_path, monkeypatch):
    dist = tmp_path / "frontend" / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<title>Stillroom</title>")
    (dist / "assets" / "app.js").write_text("console.log('ok')")
    monkeypatch.setattr(api_module, "ROOT", tmp_path)
    app = create_app(Settings(tmp_path / "data", ""))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        bad = await client.post("/api/documents", files={"file": ("bad.exe", b"Not a supported file")})
        assert bad.status_code == 422
        assert (await client.get("/")).status_code == 200
        assert (await client.get("/assets/app.js")).status_code == 200
        assert (await client.get("/api/health")).json()["groq_configured"] is False


@pytest.mark.asyncio
async def test_local_write_guard_and_safe_manifest(app, monkeypatch):
    async def fake_classify(document, api_key, model):
        return Proposal(category="Records", title="=SUM(A1:A2)",
                        summary="A record for the committee.", document_date=None,
                        date_quote="", evidence_quote="committee record", tags=[])

    monkeypatch.setattr(api_module, "classify", fake_classify)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        forbidden = await client.post("/api/documents", headers={"Origin": "https://malicious.example"},
                                      files={"file": ("record.txt", b"committee record for October filing.")})
        assert forbidden.status_code == 403
        item = await upload(client, "=cmd.txt", b"committee record for October filing.")
        for action in ("analyze", "approve", "archive"):
            response = await client.post(f"/api/documents/{item['id']}/{action}")
            assert response.status_code == 200, response.text
        rows = list(csv.reader(StringIO((await client.get("/api/manifest.csv")).text)))
        assert rows[1][1] == "'=cmd.txt"
        assert rows[1][2] == "'=SUM(A1:A2)"
