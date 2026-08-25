"""
Phase 2: SQLAlchemy ORM model for the `bookmarks` table.
Phase 3: adds the `users` table.

Deliberately a separate class from the Pydantic schemas in schemas.py - this
describes the database row (table name, column types, constraints); the
schemas describe the API contract (what a client may send/receive, with
validation rules). `BookmarkRead.model_config`'s `from_attributes=True` is
the bridge: it lets a `BookmarkRead` be built by reading attributes straight
off a `Bookmark` instance, no manual field-by-field copying.

`url` is stored as a plain string - SQL has no native "URL" column type.
Pydantic's `HttpUrl` still validates/parses it as a URL at the API boundary
in both directions (incoming payload, outgoing response); the database only
ever sees text.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Bookmark(Base):
    __tablename__ = "bookmarks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    # No client ever sets this - routes will read it off the authenticated
    # user (see get_current_user, once it exists) and stamp it on create.
    # NOT NULL: Phase 3's whole point is that every bookmark has exactly one
    # owner, not "an owner, optionally." Just a scalar FK column for now, no
    # `relationship()` - that's Phase 4's job (see Transcript_Reference_Index
    # Phase 4 row); the ownership check only ever needs
    # `bookmark.owner_id == current_user.id`, no join required.
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))


class User(Base):
    """The reference course's `User` (transcript #7) carries a UUID pk plus
    username/first_name/last_name/is_verified - out of scope for this
    project's `id` / `email` / `hashed_password` / timestamp shape (see the Phase 3
    doc's "What to Build"). `id` stays a plain autoincrement int, matching
    `Bookmark`, rather than switching primary-key styles mid-project.

    `email` is unique + indexed: login looks a user up *by* email, so this
    is the column every auth query filters on - same reasoning as an index
    on any column you `WHERE` on frequently.

    `hashed_password` never appears in a Pydantic *response* schema (see
    schemas.py once auth schemas land) - keeping it out of the schema is
    what keeps it out of any JSON response, not anything enforced here at
    the model layer. The model's only job is describing the column.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
