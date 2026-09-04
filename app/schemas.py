"""
Phase 2: Pydantic schemas - unchanged in shape from Phase 1's schema
separation (BookmarkCreate / BookmarkUpdate / BookmarkRead, one shape per
moment), moved out of main.py now that they're shared by a router module
instead of living next to the routes that used them.

The one addition: `BookmarkRead.model_config = ConfigDict(from_attributes=True)`.
Phase 1 built every `BookmarkRead` by hand from a plain dict/`BookmarkRead(...)`
call. Phase 2's routes build one from a SQLAlchemy `Bookmark` ORM object
instead - `from_attributes=True` is what allows `BookmarkRead.model_validate(orm_obj)`
(or `response_model` doing that for you) to read `orm_obj.id`, `.title`, etc.
directly off the object rather than requiring a dict.

Phase 3: adds UserCreate/UserRead, same one-shape-per-moment split. The
part that matters most here is what's *missing* from UserRead: no
`hashed_password` field. A response schema only ever serializes the fields
it declares, so a hash simply never has a way to reach a JSON response -
this is the actual enforcement point the model-layer docstring in
models.py pointed at.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl


class BookmarkCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200, examples=["FastAPI Docs"])
    url: HttpUrl = Field(examples=["https://fastapi.tiangolo.com"])
    # Phase 5: both optional, matching the model's nullable columns - a
    # bookmark doesn't need a category or description to be valid, it just
    # can't be *filtered or searched* on whichever one it skips.
    category: str | None = Field(default=None, max_length=100, examples=["docs"])
    description: str | None = Field(default=None, max_length=500)


class BookmarkUpdate(BaseModel):
    """Every field optional *with a default of None* - see learning_journal
    Phase 1 note #1. Used for PATCH: only fields actually present in the
    request body are changed (`exclude_unset=True` on the read side)."""

    title: str | None = Field(default=None, min_length=1, max_length=200, examples=["FastAPI Docs"])
    url: HttpUrl | None = Field(default=None, examples=["https://fastapi.tiangolo.com"])
    category: str | None = Field(default=None, max_length=100, examples=["docs"])
    description: str | None = Field(default=None, max_length=500)


class BookmarkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    url: HttpUrl
    category: str | None
    description: str | None
    created_at: datetime


class PaginatedBookmarks(BaseModel):
    """Phase 5's response envelope for `GET /bookmarks` - metadata a client
    needs to build pagination UI (current page, total count, page count)
    without a second round-trip just to ask "how many are there." `items`
    reuses `BookmarkRead` as-is; nothing about a single bookmark's shape
    changes just because it's now returned inside a page instead of alone."""

    items: list[BookmarkRead]
    total: int
    page: int
    size: int
    total_pages: int


class UserCreate(BaseModel):
    """`EmailStr` (needs the `email-validator` package - see
    requirements.txt) rejects malformed addresses at the API boundary, the
    same job `HttpUrl` already does for bookmark URLs. `password` is plain
    `str` here on purpose: it's the one field this schema receives but
    never re-emits - `hash_password()` (security.py) consumes it in the
    route, and only the hash ever reaches the database."""

    email: EmailStr = Field(examples=["jane@example.com"])
    password: str = Field(min_length=8, examples=["correct horse battery staple"])


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    created_at: datetime


class UserLogin(BaseModel):
    """Deliberately not reusing `UserCreate`: same two fields, but
    `password` here has no `min_length` - that rule polices what a *new*
    password must look like, not what an existing one is allowed to be. A
    correct password shorter than 8 characters should still log in; whether
    it's correct is `verify_password`'s job, not this schema's."""

    email: EmailStr = Field(examples=["jane@example.com"])
    password: str = Field(examples=["correct horse battery staple"])


class Token(BaseModel):
    """The conventional OAuth2 bearer-token response shape - `token_type`
    is what tells a client (and, later, Swagger's "Authorize" button) to
    send this back as `Authorization: Bearer <access_token>`."""

    access_token: str
    token_type: str = "bearer"


class ErrorResponse(BaseModel):
    """Phase 6: the shape `app_error_handler` (main.py) actually returns
    for every domain error - exists purely to document that shape in
    `/docs` via a route's `responses=`. Nothing in the app ever builds
    one of these directly; the handler builds the same shape by hand from
    an `AppError`, which is a plain exception, not a Pydantic model - this
    schema and that handler have to be kept in sync by hand, same as any
    other documentation describing what code actually does."""

    detail: str = Field(examples=["Bookmark not found"])
    error_code: str = Field(examples=["bookmark_not_found"])
