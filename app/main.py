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

Phase 6: one exception handler, registered for `AppError` (see
exceptions.py), replaces every route's own inline `HTTPException(...)`.
Starlette matches a raised exception to a handler by walking its class
hierarchy, so registering for the base class alone catches every
subclass - every domain error this app raises, anywhere, comes back
through this one function.

Phase 6: `CORSMiddleware`, configured from `settings.cors_origins` (empty
by default - no real frontend exists yet, see config.py). `allow_credentials`
is deliberately `False`, not just left at a cautious default: this app's
token lives in a manually-set `Authorization` header, never a cookie, so
there's no browser-attached login-proof for a credentialed CORS request to
carry in the first place - the classic wildcard-plus-credentials risk (see
the Phase 6 CORS discussion) doesn't apply to how this app actually works
today. `allow_headers=["*"]` still needs to include `Authorization`
specifically for a real cross-origin client to send it at all - `"*"`
covers that without hand-maintaining a header allowlist. Added via
`add_middleware` right after the app is created, before routers are
included - FastAPI's own CORS docs (https://fastapi.tiangolo.com/tutorial/cors/)
follow the same order.

Phase 6: `log_requests` logs one line per request - method, path, status,
duration - the same way for every route, success or domain error alike.
It doesn't need a try/except around `call_next`: a route raising
`AppError` never reaches this middleware as an exception at all -
Starlette's exception-handling layer sits *between* this middleware and
the router, so `call_next` already returns the handled error response by
the time control comes back here (see FastAPI's own middleware docs,
https://fastapi.tiangolo.com/tutorial/middleware/). `app_error_handler`
below logs a second, more specific line for domain errors - `error_code`
and `detail`, which this generic line has no way to know - the same
"errors" event the phase doc calls out, logged from the one place that
already formats every domain error.

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

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from app.config import settings
from app.exceptions import AppError
from app.logging_config import configure_logging
from app.routers import auth, bookmarks, users

configure_logging()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Nothing to do at startup/shutdown anymore - kept as a no-op lifespan
    (rather than dropped entirely) since it's still the natural place to
    add things like a connection warm-up later."""
    yield


app = FastAPI(
    title="Bookmark API",
    description=(
        "A REST API for saving and organizing bookmarks - built phase by phase. "
        "Every route lives under `/v1`. Authentication is a JWT bearer token from "
        "`/v1/auth/login`, sent as `Authorization: Bearer <token>` on every other "
        "route. Every documented non-2xx response below returns "
        '`{"detail": "...", "error_code": "..."}` - `error_code` is the stable, '
        "machine-matchable field; `detail` is free to reword."
    ),
    version="0.3.0",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "auth", "description": "Register and log in - issuing the JWT bearer token every other route requires."},
        {"name": "bookmarks", "description": "Create, read, update, delete, and query bookmarks - every route scoped to the authenticated caller's own data."},
        {"name": "users", "description": "The authenticated caller's own profile."},
        {"name": "meta", "description": "Operational endpoints for infrastructure (e.g. a liveness probe) - deliberately not versioned under /v1, see main.py's own docstring."},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/v1")
app.include_router(users.router, prefix="/v1")
app.include_router(bookmarks.router, prefix="/v1")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(f"{request.method} {request.url.path} {response.status_code} {duration_ms:.1f}ms")
    return response


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """The one place every domain error becomes an actual HTTP response.
    `error_code` is the stable, machine-matchable field; `detail` is the
    human-readable one - free to reword later without breaking a client
    that keys off `error_code` instead. `exc.headers` is `None` for most
    errors and only set where a specific error needs one (`InvalidTokenError`'s
    `WWW-Authenticate: Bearer`, per RFC 7235) - this handler doesn't need to
    know which errors need headers, only how to pass one along if present.

    The `logger.warning` here is deliberate, not incidental: it's the one
    place `error_code`/`detail` are known, so it's the one place that can
    log them - `log_requests` above only ever sees a status code, not why."""
    logger.warning(f"Domain error: {exc.error_code} - {exc.detail} ({request.method} {request.url.path})")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "error_code": exc.error_code},
        headers=exc.headers,
    )


@app.get("/health", tags=["meta"])
def health_check() -> dict[str, str]:
    """Liveness probe. Plain dict, no request validation involved."""
    return {"status": "ok"}
