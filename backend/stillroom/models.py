from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

Category = Literal["Records", "Receipts", "Projects", "Reading", "Personal", "Other"]


class Proposal(BaseModel):
    category: Category
    title: str = Field(min_length=3, max_length=100)
    summary: str = Field(min_length=8, max_length=280)
    document_date: date | None
    date_quote: str
    evidence_quote: str = Field(min_length=3, max_length=600)
    tags: list[str] = Field(max_length=5)


class ProposalUpdate(BaseModel):
    category: Category
    title: str = Field(min_length=3, max_length=100)
    document_date: date | None
    tags: list[str] = Field(max_length=5)


class Document(BaseModel):
    id: str
    original_name: str
    extension: str
    media_type: str
    size_bytes: int
    sha256: str
    created_at: datetime
    state: Literal["inbox", "ready", "archived"]
    extracted_text: str
    category: Category | None
    title: str | None
    summary: str | None
    document_date: date | None
    date_quote: str | None
    evidence_quote: str | None
    tags: list[str]
    reviewed_at: datetime | None
    archived_path: str | None
    archived_at: datetime | None
    user_edited: bool
    suggested_path: str | None = None


class Event(BaseModel):
    id: int
    document_id: str
    action: Literal["uploaded", "analyzed", "edited", "approved", "archived", "undone"]
    path: str | None
    at: datetime


class Stats(BaseModel):
    total: int
    inbox: int
    ready: int
    approved: int
    archived: int
