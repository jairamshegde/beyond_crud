"""
Phase 2: Engine, session factory, and the `get_db` dependency.

SQLite for now, sync engine and session - the Phase 2 doc's own reasoning:
sync is simpler to reason about for CRUD-scale work, and async only earns
its complexity under real concurrent I/O load. Swapping to Postgres later
(Phase 3+) means changing DATABASE_URL and connect_args here - nothing in
models.py or the routers needs to change, because they only ever depend on
`Session`, not on any SQLite-specific detail.

The library-desk analogy: `engine` is the library itself - one, long-lived,
knows how to reach the shelves. `SessionLocal()` is a librarian fetching one
book (session) for one visitor's visit. `get_db` is the front desk process:
fetch, hand it to whoever asked (`yield`), take it back when they're done
(`finally: db.close()`) - no matter how their visit went.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = "sqlite:///./bookmarks.db"

# check_same_thread=False: SQLite's default refuses to let a connection be
# used from a different thread than it was created on. FastAPI runs sync
# route functions in a worker thread pool, so without this a request can
# crash with "SQLite objects created in a thread can only be used in that
# same thread." Only needed because we picked SQLite - a Postgres URL
# wouldn't take this argument at all.
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Marker base class every ORM model inherits from. Inheriting from it
    is what registers a model's table into `Base.metadata` - the registry
    `Base.metadata.create_all(engine)` reads to know what tables to create."""


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: hands a route one fresh session, guarantees it's
    closed afterward - even if the route raises. `db.commit()` is
    deliberately NOT called here; each route commits explicitly after its
    own write, so a route that fails partway through never commits a
    half-finished change (see Phase 2 doc's interview trap #5)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
