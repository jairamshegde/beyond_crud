"""
Phase 2: Database & Dependency Injection

Swaps Phase 1's in-memory dict for a real SQLite database via SQLAlchemy,
and introduces FastAPI's dependency injection (`get_db`) to hand every route
a session and guarantee it's closed afterward. The API contract itself -
routes, schemas, status codes, PUT-vs-PATCH - is unchanged from Phase 1;
only what's behind the routes changed, which is the point of separating
schemas from storage in the first place.

The single main.py file from Phase 0/1 is now split into modules
(database.py, models.py, schemas.py, routers/bookmarks.py) - see
`4-Modular Project Structure With FastAPI Routers.txt` in the reference
course for the precedent, done here at the same point the DB was
introduced rather than after.
"""

from contextlib import asynccontextmanager

from sqlalchemy import select

from fastapi import FastAPI

from app.database import Base, SessionLocal, engine
from app.models import Bookmark
from app.routers import bookmarks


def _seed_dummy_data() -> None:
    """Seed a couple of rows so GET has data without needing a POST first -
    same convenience Phase 1 had, but guarded: unlike the in-memory dict,
    this database persists across restarts, so seeding unconditionally
    every startup would duplicate rows on the second run onward."""
    with SessionLocal() as db:
        if db.execute(select(Bookmark)).first() is not None:
            return
        db.add_all(
            [
                Bookmark(title="FastAPI Docs", url="https://fastapi.tiangolo.com"),
                Bookmark(title="Pydantic Docs", url="https://docs.pydantic.dev"),
            ]
        )
        db.commit()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Runs once at startup (before `yield`) and once at shutdown (after) -
    the same setup/teardown split `get_db` uses, at the scale of the whole
    app instead of a single request. `create_all` reads `Base.metadata`
    (populated by importing `app.models`, which registers `Bookmark` onto
    it) and creates any table that doesn't already exist yet - it never
    touches a table that's already there."""
    Base.metadata.create_all(bind=engine)
    _seed_dummy_data()
    yield


app = FastAPI(
    title="Bookmark API",
    description="A REST API for saving and organizing bookmarks - built phase by phase.",
    version="0.3.0",
    lifespan=lifespan,
)

app.include_router(bookmarks.router)


@app.get("/health", tags=["meta"])
def health_check() -> dict[str, str]:
    """Liveness probe. Plain dict, no request validation involved."""
    return {"status": "ok"}
