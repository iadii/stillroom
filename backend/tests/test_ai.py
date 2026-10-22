import json
from datetime import date, datetime, timezone

import httpx
import pytest

from stillroom.ai import AIError, classify, verify_proposal
from stillroom.models import Document, Proposal


def document() -> Document:
    return Document(
        id="doc", original_name="garden.txt", extension=".txt", media_type="text/plain",
        size_bytes=120, sha256="abc", created_at=datetime.now(timezone.utc), state="inbox",
        extracted_text="Community garden meeting notes dated October 22, 2026. We planned the fall planting day.",
        category=None, title=None, summary=None, document_date=None, date_quote=None,
        evidence_quote=None, tags=[], reviewed_at=None, archived_path=None,
        archived_at=None, user_edited=False,
    )


def proposal(**changes) -> Proposal:
    data = dict(category="Projects", title="Fall planting plan", summary="Meeting notes for fall planting.",
                document_date=date(2026, 10, 22), date_quote="October 22, 2026",
                evidence_quote="We planned the fall planting day.", tags=["garden"])
    return Proposal(**(data | changes))


def test_quote_and_date_checks():
    assert verify_proposal(proposal(), document()).document_date == date(2026, 10, 22)
    wrong_date = verify_proposal(proposal(document_date=date(2026, 10, 23)), document())
    assert wrong_date.document_date is None
    assert wrong_date.date_quote == ""
    with pytest.raises(AIError):
        verify_proposal(proposal(evidence_quote="The meeting was cancelled."), document())


@pytest.mark.asyncio
async def test_provider_request_uses_strict_schema_and_server_key(monkeypatch):
    seen = {}

    def respond(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        content = proposal().model_dump(mode="json")
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(content)}}]})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: real_client(transport=httpx.MockTransport(respond)))
    result = await classify(document(), "test-secret", "openai/gpt-oss-120b")
    assert seen["url"].endswith("/chat/completions")
    assert seen["auth"] == "Bearer test-secret"
    assert seen["body"]["response_format"]["json_schema"]["strict"] is True
    assert result.title == "Fall planting plan"
