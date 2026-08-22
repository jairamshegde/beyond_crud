"""
Phase 1: In-Memory CRUD - Schema Separation & Error Handling

Full CRUD over the in-memory store, built on Phase 0's foundation:
- Pydantic schema separation: BookmarkCreate / BookmarkUpdate / BookmarkRead,
  each shaped for the one moment it's used in (what a client may send to
  create, what a client may send to change, what the server hands back).
- Explicit domain errors via HTTPException (404), distinct from the
  automatic 422 Pydantic validation already gives us for free.
- PUT vs PATCH, built side by side to make the difference real rather than
  theoretical: PUT is full replacement (requires the complete
  BookmarkCreate-shaped body, id/created_at untouched), PATCH is a partial
  merge (BookmarkUpdate, every field optional, only sent fields change).

Still a single file, still an in-memory dict - a real database replaces
this in Phase 2 without the API contract (these schemas, these routes)
needing to change.
"""

from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field, HttpUrl

app = FastAPI(
    title="Bookmark API",
    description="A REST API for saving and organizing bookmarks - built phase by phase.",
    version="0.2.0",
)


# --------------------------------------------------------------------------
# Schemas (Pydantic v2)
# --------------------------------------------------------------------------
# Three shapes for three different moments: what a client may send to
# create, what a client may send to change, and what the server always
# hands back. `id` and `created_at` are server-owned - no client input
# model ever includes them.


class BookmarkCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200, examples=["FastAPI Docs"])
    url: HttpUrl = Field(examples=["https://fastapi.tiangolo.com"])


class BookmarkUpdate(BaseModel):
    """Every field optional *with a default of None* - not just optionally
    typed. `str | None` alone would still require the key to be present
    (just nullable); `= None` is what makes omitting it legal. Used for
    PATCH: only the fields actually present in the request body are
    changed (see `exclude_unset=True` below)."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    url: HttpUrl | None = None


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

_id_seq = 0
_bookmarks_db: dict[int, BookmarkRead] = {}


def _seed_dummy_data() -> None:
    global _id_seq
    for item in (
        BookmarkCreate(title="FastAPI Docs", url="https://fastapi.tiangolo.com"),
        BookmarkCreate(title="Pydantic Docs", url="https://docs.pydantic.dev"),
    ):
        _id_seq += 1
        bookmark_id = _id_seq
        _bookmarks_db[bookmark_id] = BookmarkRead(
            id=bookmark_id,
            title=item.title,
            url=item.url,
            created_at=datetime.now(timezone.utc),
        )


_seed_dummy_data()


def _get_bookmark_or_404(bookmark_id: int) -> BookmarkRead:
    """Shared lookup for every route that needs an existing bookmark
    (GET-one, PUT, PATCH, DELETE). This is the domain-error check Pydantic
    can't do for us: the id is a perfectly valid int (422 already passed),
    but there's no guarantee it's a key in `_bookmarks_db`."""
    bookmark = _bookmarks_db.get(bookmark_id)
    if bookmark is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bookmark not found")
    return bookmark


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------


@app.get("/health", tags=["meta"])
def health_check() -> dict[str, str]:
    """Liveness probe. Plain dict, no request validation involved."""
    return {"status": "ok"}


@app.get("/bookmarks", response_model=list[BookmarkRead], tags=["bookmarks"])
def list_bookmarks() -> list[BookmarkRead]:
    """Collection endpoint - every bookmark currently in the store."""
    return list(_bookmarks_db.values())


# NOTE on route ordering: a static segment ("search") must be declared
# BEFORE a dynamic segment in the same position ("{bookmark_id}"). FastAPI
# matches routes in registration order, so if `/bookmarks/{bookmark_id}`
# were declared first, a request to `/bookmarks/search` would be captured
# by it and fail int-conversion on "search" instead of reaching this route.
@app.get("/bookmarks/search", response_model=list[BookmarkRead], tags=["bookmarks"])
def search_bookmarks_db(q: str | None = None) -> list[BookmarkRead]:
    """Query parameter example: `q` is optional (defaults to None) and
    filters bookmarks by a case-insensitive title match."""
    if q is None:
        return list(_bookmarks_db.values())
    needle = q.lower()
    return [b for b in _bookmarks_db.values() if needle in b.title.lower()]


@app.get("/bookmarks/{bookmark_id}", response_model=BookmarkRead, tags=["bookmarks"])
def get_bookmark(bookmark_id: int) -> BookmarkRead:
    """Path parameter example: FastAPI converts/validates `bookmark_id` to
    `int` from the URL before this function body ever runs; a non-integer
    segment (other than "search", matched above) yields a 422 automatically.
    A well-formed but nonexistent id is a domain error, not a validation
    error - that's what `_get_bookmark_or_404` is for."""
    return _get_bookmark_or_404(bookmark_id)


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
    global _id_seq
    _id_seq += 1
    bookmark_id = _id_seq
    bookmark = BookmarkRead(
        id=bookmark_id,
        title=payload.title,
        url=payload.url,
        created_at=datetime.now(timezone.utc),
    )
    _bookmarks_db[bookmark_id] = bookmark
    return bookmark


@app.put("/bookmarks/{bookmark_id}", response_model=BookmarkRead, tags=["bookmarks"])
def replace_bookmark(bookmark_id: int, payload: BookmarkCreate) -> BookmarkRead:
    """Full replacement, spec-correct PUT: the body must be a complete
    `BookmarkCreate` (title AND url both required - Pydantic 422s if either
    is missing, no partial bodies accepted). Every client-writable field is
    overwritten wholesale from the payload; nothing is merged. `id` and
    `created_at` are server-owned and untouched - they were never part of
    what the client sent in the first place, so there's nothing to
    "replace" about them. Calling this twice with the same body is a no-op
    the second time - that's the idempotency PUT promises."""
    existing = _get_bookmark_or_404(bookmark_id)
    updated = BookmarkRead(
        id=existing.id,
        title=payload.title,
        url=payload.url,
        created_at=existing.created_at,
    )
    _bookmarks_db[bookmark_id] = updated
    return updated


@app.patch("/bookmarks/{bookmark_id}", response_model=BookmarkRead, tags=["bookmarks"])
def update_bookmark(bookmark_id: int, payload: BookmarkUpdate) -> BookmarkRead:
    """Partial update: the body is `BookmarkUpdate`, every field optional.
    `exclude_unset=True` is the key line - it gives back a dict containing
    ONLY the keys the client actually sent, not every field defaulted to
    None. Without it, an omitted `url` would come through as `None` and
    silently null out data the client never touched."""
    existing = _get_bookmark_or_404(bookmark_id)
    changes = payload.model_dump(exclude_unset=True)
    updated = existing.model_copy(update=changes)
    _bookmarks_db[bookmark_id] = updated
    return updated


@app.delete("/bookmarks/{bookmark_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["bookmarks"])
def delete_bookmark(bookmark_id: int) -> None:
    """204 No Content: the request succeeded and there's nothing to return.
    FastAPI won't let a 204 response carry a body, so the function returns
    nothing (None) - returning the deleted bookmark here would be a
    contract violation of the status code itself."""
    _get_bookmark_or_404(bookmark_id)
    del _bookmarks_db[bookmark_id]
