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
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


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
