"""
Phase 2: Database & Dependency Injection
Phase 3: Alembic replaces create_all as the source of schema truth.

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

Phase 6: every router now mounts under `/v1` - `prefix="/v1"` passed to
`include_router` here, layered on top of each router's own `/auth`/
`/users`/`/bookmarks` prefix, so `/v1` + `/auth` = `/v1/auth`. Nothing
about the routers themselves changed; only where they're mounted. `/health`
deliberately stays un-versioned - it's a liveness probe infrastructure
polls, not part of the API's data contract, and that tooling expects a
stable path regardless of which API version exists behind it.

Phase 2's lifespan used to call `Base.metadata.create_all(bind=engine)` on
every startup and seed a couple of dummy bookmarks. Both are gone now:
- `create_all` and Alembic were two mechanisms both claiming to own the
  schema; now that every change goes through a migration (see migrations/),
  the app process itself has no business creating tables - a real deploy
  runs `alembic upgrade head` before the app ever starts, same as this
  project's own workflow going forward.
- The dummy seed rows had no owner, and Phase 3's whole point is that every
  bookmark belongs to exactly one user - there's no meaningful "anonymous"
  bookmark to seed anymore. Once /auth/register exists, seeing real data
  means registering a user and creating bookmarks as them.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.routers import auth, bookmarks, users


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Nothing to do at startup/shutdown anymore - kept as a no-op lifespan
    (rather than dropped entirely) since it's still the natural place to
    add things like a connection warm-up later."""
    yield


app = FastAPI(
    title="Bookmark API",
    description="A REST API for saving and organizing bookmarks - built phase by phase.",
    version="0.3.0",
    lifespan=lifespan,
)

app.include_router(auth.router, prefix="/v1")
app.include_router(users.router, prefix="/v1")
app.include_router(bookmarks.router, prefix="/v1")


@app.get("/health", tags=["meta"])
def health_check() -> dict[str, str]:
    """Liveness probe. Plain dict, no request validation involved."""
    return {"status": "ok"}
