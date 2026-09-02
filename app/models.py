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
    # Phase 5: both nullable, both optional at the API boundary too (see
    # schemas.py) - existing rows have neither, and there's no sensible
    # default to backfill ("uncategorized"? empty string?) so NULL is the
    # honest representation of "never set," not a stand-in value.
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # No client ever sets this - routes will read it off the authenticated
    # user (see get_current_user, once it exists) and stamp it on create.
    # NOT NULL: Phase 3's whole point is that every bookmark has exactly one
    # owner, not "an owner, optionally." Just a scalar FK column, no
    # `relationship()` - the ownership check only ever needs
    # `bookmark.owner_id == current_user.id`, a plain comparison, no join
    # required. No phase on the current roadmap needs `user.bookmarks`-style
    # navigation, so there's nothing a `relationship()` would earn its keep
    # doing yet; add one if and when a real need for that navigation shows up.
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))


class User(Base):
    """Deliberately minimal - `id` / `email` / `hashed_password` / timestamp
    is everything this project's "What to Build" actually needs (see the
    Phase 3 doc); no username, no first/last name, no verification flag.
    `id` stays a plain autoincrement int, matching `Bookmark`, rather than
    reaching for a UUID primary key this project has no need for.

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
