"""
Phase 2: Bookmark CRUD routes, refactored from Phase 1's in-memory dict to
a real SQLite database via SQLAlchemy.

The route bodies barely changed in shape from Phase 1 - same status codes,
same `HTTPException` 404s, same PUT-vs-PATCH split. What changed is every
route now declares `db: Session = Depends(get_db)`: FastAPI resolves that
before the route body runs (see the library-front-desk analogy), hands in a
session, and closes it after the response is sent - no route has to open or
close anything itself.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException, status

from app.database import get_db
from app.models import Bookmark
from app.schemas import BookmarkCreate, BookmarkRead, BookmarkUpdate

router = APIRouter(prefix="/bookmarks", tags=["bookmarks"])


def _get_bookmark_or_404(db: Session, bookmark_id: int) -> Bookmark:
    """Shared lookup for every route that needs an existing bookmark. Same
    domain-error role as Phase 1's version: `bookmark_id` is a valid int
    (422 already passed), but there's no guarantee a row with that id
    exists. `Session.get` is SQLAlchemy's primary-key lookup - it returns
    the ORM object or `None`, never raises on a miss."""
    bookmark = db.get(Bookmark, bookmark_id)
    if bookmark is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bookmark not found")
    return bookmark


@router.get("", response_model=list[BookmarkRead])
def list_bookmarks(db: Session = Depends(get_db)) -> list[Bookmark]:
    """Collection endpoint - every bookmark currently in the table.
    `response_model=list[BookmarkRead]` is what turns each `Bookmark` ORM
    object into a `BookmarkRead` on the way out, via `from_attributes`."""
    return db.execute(select(Bookmark)).scalars().all()


# NOTE on route ordering: a static segment ("search") must be declared
# BEFORE a dynamic segment in the same position ("{bookmark_id}") - same
# reasoning as Phase 1, unchanged by the move to a database.
@router.get("/search", response_model=list[BookmarkRead])
def search_bookmarks(q: str | None = None, db: Session = Depends(get_db)) -> list[Bookmark]:
    """Query parameter example: `q` optional, case-insensitive title match.
    `ilike` pushes the filtering into the database itself (a `WHERE` clause)
    instead of pulling every row into Python first."""
    stmt = select(Bookmark)
    if q is not None:
        stmt = stmt.where(Bookmark.title.ilike(f"%{q}%"))
    return db.execute(stmt).scalars().all()


@router.get("/{bookmark_id}", response_model=BookmarkRead)
def get_bookmark(bookmark_id: int, db: Session = Depends(get_db)) -> Bookmark:
    return _get_bookmark_or_404(db, bookmark_id)


@router.post("", response_model=BookmarkRead, status_code=status.HTTP_201_CREATED)
def create_bookmark(payload: BookmarkCreate, db: Session = Depends(get_db)) -> Bookmark:
    """`payload.url` is a Pydantic `HttpUrl` object, not a plain string -
    `str(...)` is what converts it to the text SQLite actually stores.
    `db.add` only stages the insert (see the Unit-of-Work explanation);
    `db.commit` is what sends the SQL and ends the transaction; `db.refresh`
    reloads the row afterward so the returned object has the id and
    `created_at` the database actually assigned."""
    bookmark = Bookmark(title=payload.title, url=str(payload.url))
    db.add(bookmark)
    db.commit()
    db.refresh(bookmark)
    return bookmark


@router.put("/{bookmark_id}", response_model=BookmarkRead)
def replace_bookmark(
    bookmark_id: int, payload: BookmarkCreate, db: Session = Depends(get_db)
) -> Bookmark:
    """Full replacement: `BookmarkCreate` requires both `title` and `url`,
    so a `PUT` missing either 422s before this body ever runs. Every
    client-writable field is overwritten wholesale; `id`/`created_at` are
    server-owned and untouched."""
    bookmark = _get_bookmark_or_404(db, bookmark_id)
    bookmark.title = payload.title
    bookmark.url = str(payload.url)
    db.commit()
    db.refresh(bookmark)
    return bookmark


@router.patch("/{bookmark_id}", response_model=BookmarkRead)
def update_bookmark(
    bookmark_id: int, payload: BookmarkUpdate, db: Session = Depends(get_db)
) -> Bookmark:
    """Partial update: `exclude_unset=True` keeps only the keys the client
    actually sent (see learning_journal Phase 1 note #2) - `setattr` then
    applies just those onto the tracked ORM object. Because `bookmark` came
    from this same session, mutating its attributes is enough for the
    session to know it's "dirty" and needs an `UPDATE`; `commit()` is what
    actually sends it."""
    bookmark = _get_bookmark_or_404(db, bookmark_id)
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        if field == "url":
            value = str(value)
        setattr(bookmark, field, value)
    db.commit()
    db.refresh(bookmark)
    return bookmark


@router.delete("/{bookmark_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bookmark(bookmark_id: int, db: Session = Depends(get_db)) -> None:
    bookmark = _get_bookmark_or_404(db, bookmark_id)
    db.delete(bookmark)
    db.commit()
