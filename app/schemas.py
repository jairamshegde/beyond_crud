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


class BookmarkUpdate(BaseModel):
    """Every field optional *with a default of None* - see learning_journal
    Phase 1 note #1. Used for PATCH: only fields actually present in the
    request body are changed (`exclude_unset=True` on the read side)."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    url: HttpUrl | None = None


class BookmarkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    url: HttpUrl
    created_at: datetime


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
