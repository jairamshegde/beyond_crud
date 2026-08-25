"""
Phase 2: Bookmark CRUD routes, refactored from Phase 1's in-memory dict to
a real SQLite database via SQLAlchemy.
Phase 3: every route now requires `get_current_user`, and every query is
scoped to the caller's own bookmarks - authentication (who are you) plus
authorization (is this yours) from the Phase 3 doc, made concrete.

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
from app.dependencies import get_current_user
from app.models import Bookmark, User
from app.schemas import BookmarkCreate, BookmarkRead, BookmarkUpdate

router = APIRouter(prefix="/bookmarks", tags=["bookmarks"])


def _get_bookmark_or_404(db: Session, bookmark_id: int, owner_id: int) -> Bookmark:
    """Shared lookup for every route that needs an existing bookmark -
    now scoped to `owner_id` as part of the same query, not a separate
    check afterward. A bookmark that exists but belongs to someone else
    and a bookmark that doesn't exist at all produce the identical 404 -
    same reasoning as login's single "invalid email or password" and
    get_current_user's single "invalid or expired token": a stranger can't
    tell "not yours" apart from "doesn't exist" by the response they get.
    """
    stmt = select(Bookmark).where(Bookmark.id == bookmark_id, Bookmark.owner_id == owner_id)
    bookmark = db.execute(stmt).scalar_one_or_none()
    if bookmark is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bookmark not found")
    return bookmark


@router.get("", response_model=list[BookmarkRead])
def list_bookmarks(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> list[Bookmark]:
    """Collection endpoint - every bookmark *this user* owns, not every
    bookmark in the table. `response_model=list[BookmarkRead]` is what
    turns each `Bookmark` ORM object into a `BookmarkRead` on the way out,
    via `from_attributes`."""
    stmt = select(Bookmark).where(Bookmark.owner_id == current_user.id)
    return db.execute(stmt).scalars().all()


# NOTE on route ordering: a static segment ("search") must be declared
# BEFORE a dynamic segment in the same position ("{bookmark_id}") - same
# reasoning as Phase 1, unchanged by the move to a database.
@router.get("/search", response_model=list[BookmarkRead])
def search_bookmarks(
    q: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Bookmark]:
    """Query parameter example: `q` optional, case-insensitive title match.
    `ilike` pushes the filtering into the database itself (a `WHERE` clause)
    instead of pulling every row into Python first. The owner filter is
    always applied, `q` is layered on top of it - so a search is a search
    *within your own bookmarks*, never across everyone's."""
    stmt = select(Bookmark).where(Bookmark.owner_id == current_user.id)
    if q is not None:
        stmt = stmt.where(Bookmark.title.ilike(f"%{q}%"))
    return db.execute(stmt).scalars().all()


@router.get("/{bookmark_id}", response_model=BookmarkRead)
def get_bookmark(
    bookmark_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Bookmark:
    return _get_bookmark_or_404(db, bookmark_id, current_user.id)


@router.post("", response_model=BookmarkRead, status_code=status.HTTP_201_CREATED)
def create_bookmark(
    payload: BookmarkCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Bookmark:
    """`payload.url` is a Pydantic `HttpUrl` object, not a plain string -
    `str(...)` is what converts it to the text SQLite actually stores.
    `owner_id=current_user.id` is the stamp from the intuition explanation
    made real: `BookmarkCreate` has no `owner_id` field at all (see
    schemas.py), so there's no client-supplied value to even consider -
    ownership always comes from the token, never the request body.
    `db.add` only stages the insert (see the Unit-of-Work explanation);
    `db.commit` is what sends the SQL and ends the transaction; `db.refresh`
    reloads the row afterward so the returned object has the id and
    `created_at` the database actually assigned."""
    bookmark = Bookmark(title=payload.title, url=str(payload.url), owner_id=current_user.id)
    db.add(bookmark)
    db.commit()
    db.refresh(bookmark)
    return bookmark


@router.put("/{bookmark_id}", response_model=BookmarkRead)
def replace_bookmark(
    bookmark_id: int,
    payload: BookmarkCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Bookmark:
    """Full replacement: `BookmarkCreate` requires both `title` and `url`,
    so a `PUT` missing either 422s before this body ever runs. Every
    client-writable field is overwritten wholesale; `id`/`created_at`/
    `owner_id` are server-owned and untouched - ownership can't be
    transferred by editing a PUT body, because there's nowhere in
    `BookmarkCreate` to even put a new owner."""
    bookmark = _get_bookmark_or_404(db, bookmark_id, current_user.id)
    bookmark.title = payload.title
    bookmark.url = str(payload.url)
    db.commit()
    db.refresh(bookmark)
    return bookmark


@router.patch("/{bookmark_id}", response_model=BookmarkRead)
def update_bookmark(
    bookmark_id: int,
    payload: BookmarkUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Bookmark:
    """Partial update: `exclude_unset=True` keeps only the keys the client
    actually sent (see learning_journal Phase 1 note #2) - `setattr` then
    applies just those onto the tracked ORM object. Because `bookmark` came
    from this same session, mutating its attributes is enough for the
    session to know it's "dirty" and needs an `UPDATE`; `commit()` is what
    actually sends it."""
    bookmark = _get_bookmark_or_404(db, bookmark_id, current_user.id)
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        if field == "url":
            value = str(value)
        setattr(bookmark, field, value)
    db.commit()
    db.refresh(bookmark)
    return bookmark


@router.delete("/{bookmark_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bookmark(
    bookmark_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    bookmark = _get_bookmark_or_404(db, bookmark_id, current_user.id)
    db.delete(bookmark)
    db.commit()
