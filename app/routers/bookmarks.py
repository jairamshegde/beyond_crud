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

Phase 5: `list_bookmarks` grows from "every bookmark this user owns" into a
filtered, sorted, paginated query, built one conditional `.where()` at a
time. The old dedicated `/bookmarks/search?q=` route is gone - its whole
job (case-insensitive title search) is now a subset of what `search` does
here (title OR description), so keeping both would just be two competing
ways to do the same thing.

Phase 6: `_get_bookmark_or_404`'s inline `HTTPException` is now
`raise BookmarkNotFoundError()` (see exceptions.py) - this file no longer
decides what a 404 looks like, just that one happened. The single handler
registered in main.py does the formatting, the same way for every domain
error in the app, not just this one.
"""

from typing import Literal, get_args

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, Query, status

from app.database import get_db
from app.dependencies import get_current_user
from app.exceptions import BookmarkNotFoundError
from app.models import Bookmark, User
from app.schemas import BookmarkCreate, BookmarkRead, BookmarkUpdate, PaginatedBookmarks

router = APIRouter(prefix="/bookmarks", tags=["bookmarks"])

# Phase 5's allowlist - one source of truth, not two. Originally this was
# a hand-written dict AND a separately hand-written `Literal[...]` on the
# `sort_by` parameter below, kept in sync only by remembering to edit both
# every time - a code review caught it: nothing enforced they'd ever agree,
# so a future edit to one and not the other could pass FastAPI's 422 check
# with a `sort_by` this dict doesn't recognize, `KeyError`-crashing into an
# unhandled 500 instead of the clean rejection the allowlist was supposed
# to guarantee.
#
# `SortBy` is now the only place these names are written - a real `Literal`
# type, so FastAPI/Pydantic and any static type checker both understand it
# fully (an earlier attempt at deriving the Literal itself via `Literal[
# *_SORT_FIELDS]` unpacking runs fine but isn't valid to a type checker -
# Pyright flagged it immediately, so it's not actually the single source of
# truth it looked like). `_SORT_COLUMNS` is what's derived from it instead,
# via `get_args()`, which only ever reads the Literal - it doesn't retype it.
# `getattr(Bookmark, name)` is safe here specifically because `name` walks
# that Literal's own values - written in this file, never the client's
# string. The client's `sort_by` only ever becomes a dict key into the
# *already built* `_SORT_COLUMNS`, the same menu-not-recipe-card rule as
# before.
SortBy = Literal["created_at", "title"]
_SORT_COLUMNS = {name: getattr(Bookmark, name) for name in get_args(SortBy)}


def _escape_like(value: str) -> str:
    """`ilike`'s pattern language treats `%` (any run of characters) and
    `_` (any single character) as wildcards, not literal text - a code
    review caught that `search` was being dropped straight into a pattern
    unescaped, so a literal `%` or `_` typed by a user silently turned into
    a wildcard instead of the character they meant. Backslash-escaping each
    one first (and the escape character itself, so a literal `\\` in the
    input can't accidentally escape the *next* character) is what makes the
    following `.ilike(pattern, escape="\\")` treat the user's text as text.
    """
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


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
        raise BookmarkNotFoundError()
    return bookmark


@router.get("", response_model=PaginatedBookmarks)
def list_bookmarks(
    category: str | None = Query(default=None, description="Exact category match"),
    search: str | None = Query(
        default=None, description="Case-insensitive substring match against title or description"
    ),
    sort_by: SortBy = Query(default="created_at"),
    order: Literal["asc", "desc"] = Query(default="desc"),
    page: int = Query(default=1, ge=1, description="1-indexed page number"),
    size: int = Query(default=20, ge=1, le=100, description="Items per page, capped at 100"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedBookmarks:
    """Collection endpoint - every bookmark *this user* owns, narrowed and
    arranged by whichever query parameters were actually sent (the
    librarian, not a vending machine - one endpoint, described by the
    request rather than picked by it).

    Built as one query, one topping at a time: start from the owner-scoped
    base, layer on `category`/`search` only if provided, then order and
    page the *filtered* set. `total` has to be counted from the filtered
    set BEFORE `.limit()`/`.offset()` are applied - otherwise it would just
    report how many rows came back on this one page, not how many exist
    across all of them.
    """
    stmt = select(Bookmark).where(Bookmark.owner_id == current_user.id)
    if category is not None:
        stmt = stmt.where(Bookmark.category == category)
    if search is not None:
        pattern = f"%{_escape_like(search)}%"
        stmt = stmt.where(
            or_(
                Bookmark.title.ilike(pattern, escape="\\"),
                Bookmark.description.ilike(pattern, escape="\\"),
            )
        )

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()

    sort_column = _SORT_COLUMNS[sort_by]
    stmt = stmt.order_by(sort_column.asc() if order == "asc" else sort_column.desc())
    stmt = stmt.offset((page - 1) * size).limit(size)
    items = db.execute(stmt).scalars().all()

    total_pages = (total + size - 1) // size  # ceiling division; 0 when total is 0
    return PaginatedBookmarks(items=items, total=total, page=page, size=size, total_pages=total_pages)


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
    bookmark = Bookmark(
        title=payload.title,
        url=str(payload.url),
        category=payload.category,
        description=payload.description,
        owner_id=current_user.id,
    )
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
    bookmark.category = payload.category
    bookmark.description = payload.description
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
