# Test Suite

Run with `pytest` from the project root (needs the `beyondcrud` conda env active).

## What this covers (Phase 4: Testing Foundations)

This is the *foundation* - the tooling, plus tests backfilled for everything that
shipped without them in Phases 1-3:

- `test_auth.py` - registration, login, and the anti-enumeration failure shape.
- `test_get_current_user.py` - every way a token can fail to authenticate, and that
  `get_current_user`'s own failure modes are indistinguishable from each other.
- `test_bookmarks.py` - full CRUD happy path, ownership scoping (a bookmark that
  isn't yours is a 404, not a 403), and schema validation (422s).

## What this covers (Phase 5: Advanced Querying)

- `test_bookmark_query.py` - `GET /bookmarks`'s filters (category, search across
  title/description), sorting (both directions, the sort-column allowlist),
  pagination (page/size boundaries, the size cap), and the invalid-query-param
  422s - written alongside the endpoint itself, per the Phase 4 doc's whole point.
- `test_bookmarks.py` also gained a PUT-vs-PATCH case: a PUT that omits
  `category`/`description` clears them (full replacement, not a merge) -
  documenting that as deliberate rather than a silent side effect.

## What this deliberately does not cover yet

Foundation, not full coverage - each of these belongs to the phase that actually
introduces the surface it would be testing:

- CORS headers, custom exception handler shapes, rate-limit rejection - **Phase 6**.
- Background task / Celery task execution and failure handling - **Phase 8A/8B**.
- WebSocket connection lifecycle and broadcast delivery - **Phase 8C**.
- Concurrent-access races (lost updates) under real Postgres - **Phase 7**, once
  there's a real database capable of exhibiting them (SQLite's single-writer lock
  makes this class of bug impossible to reproduce here).

Coverage is expected to keep growing every phase from here forward, not arrive all
at once.
