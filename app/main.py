"""
Phase 0: FastAPI Fundamentals - Bookmark API

Covers the foundational request lifecycle:
- Routing: path parameters vs. query parameters
- Request validation via Pydantic models
- Response serialization via `response_model`
- Automatic OpenAPI docs at /docs (Swagger) and /redoc

Deliberately a single file with a plain in-memory dict standing in for a
database - just enough state so GET/POST return real data. Real CRUD
(update/delete, proper create/update/read schema separation) starts in
Phase 1; a real database replaces this dict in Phase 2.
"""

from datetime import datetime, timezone
from itertools import count

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field, HttpUrl

app = FastAPI(
    title="Bookmark API",
    description="A REST API for saving and organizing bookmarks - built phase by phase.",
    version="0.1.0",
)


# --------------------------------------------------------------------------
# Schemas (Pydantic v2)
# --------------------------------------------------------------------------
# Phase 0 keeps one input model and one output model. Phase 1 splits this
# into BookmarkCreate / BookmarkUpdate / BookmarkRead once real CRUD lands.


class BookmarkCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200, examples=["FastAPI Docs"])
    url: HttpUrl = Field(examples=["https://fastapi.tiangolo.com"])


class BookmarkRead(BaseModel):
    id: int
    title: str
    url: HttpUrl
    created_at: datetime


# --------------------------------------------------------------------------
# "Storage" - an in-memory dict standing in for a database (Phase 2 swaps
# this for SQLAlchemy). Seeded with a couple of rows so GET has data to
# return without needing a POST first.
# --------------------------------------------------------------------------

_id_seq = count(start=1)
_bookmarks: dict[int, BookmarkRead] = {}


def _seed() -> None:
    for item in (
        BookmarkCreate(title="FastAPI Docs", url="https://fastapi.tiangolo.com"),
        BookmarkCreate(title="Pydantic Docs", url="https://docs.pydantic.dev"),
    ):
        bookmark_id = next(_id_seq)
        _bookmarks[bookmark_id] = BookmarkRead(
            id=bookmark_id,
            title=item.title,
            url=item.url,
            created_at=datetime.now(timezone.utc),
        )


_seed()


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------


@app.get("/health", tags=["meta"])
def health_check() -> dict[str, str]:
    """Liveness probe. Plain dict, no request validation involved."""
    return {"status": "ok"}


# NOTE on route ordering: a static segment ("search") must be declared
# BEFORE a dynamic segment in the same position ("{bookmark_id}"). FastAPI
# matches routes in registration order, so if `/bookmarks/{bookmark_id}`
# were declared first, a request to `/bookmarks/search` would be captured
# by it and fail int-conversion on "search" instead of reaching this route.
@app.get("/bookmarks/search", response_model=list[BookmarkRead], tags=["bookmarks"])
def search_bookmarks(q: str | None = None) -> list[BookmarkRead]:
    """Query parameter example: `q` is optional (defaults to None) and
    filters bookmarks by a case-insensitive title match."""
    if q is None:
        return list(_bookmarks.values())
    needle = q.lower()
    return [b for b in _bookmarks.values() if needle in b.title.lower()]


@app.get("/bookmarks/{bookmark_id}", response_model=BookmarkRead, tags=["bookmarks"])
def get_bookmark(bookmark_id: int) -> BookmarkRead:
    """Path parameter example: FastAPI converts/validates `bookmark_id` to
    `int` from the URL before this function body ever runs; a non-integer
    segment (other than "search", matched above) yields a 422 automatically."""
    bookmark = _bookmarks.get(bookmark_id)
    if bookmark is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bookmark not found")
    return bookmark


@app.post(
    "/bookmarks",
    response_model=BookmarkRead,
    status_code=status.HTTP_201_CREATED,
    tags=["bookmarks"],
)
def create_bookmark(payload: BookmarkCreate) -> BookmarkRead:
    """Request body example: `payload` is parsed from JSON and validated
    against `BookmarkCreate` (a 422 is returned automatically if it doesn't
    match). `response_model` then filters/validates the outgoing data against
    `BookmarkRead` - the client only ever sees fields declared there."""
    bookmark_id = next(_id_seq)
    bookmark = BookmarkRead(
        id=bookmark_id,
        title=payload.title,
        url=payload.url,
        created_at=datetime.now(timezone.utc),
    )
    _bookmarks[bookmark_id] = bookmark
    return bookmark
