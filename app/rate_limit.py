"""
Phase 6: the shared `Limiter` instance - lives in its own module (not
main.py) because routers/auth.py needs to import it to decorate
`register`/`login`, and main.py already imports routers/auth.py; putting
`limiter` in main.py would make that a circular import, same reason
`get_db` lives in database.py rather than inside any one router.

`key_func=get_remote_address` is the "gate on where, not who" idea from
the Phase 6 rate-limiting discussion, made concrete: there's no verified
identity yet on `/auth/login`/`/auth/register`, so the caller's IP is
what a hit gets counted against - see slowapi's own `util.get_remote_address`.

No `SlowAPIMiddleware` here, deliberately: confirmed directly from
slowapi's source that a route carrying its own `@limiter.limit(...)`
decorator is fully self-enforcing (`_should_exempt` in slowapi/middleware.py
explicitly skips any route already in `limiter._route_limits`, "we let the
decorator handle it") - the middleware only matters for a global
default limit applied to *undecorated* routes, which this app doesn't
have. Adding it would be inert extra wiring for a case that doesn't exist
here.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
