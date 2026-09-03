"""
Phase 6: Domain exceptions and the single handler that formats all of them.

Every error here is a known, on-purpose condition the API needs to report -
not a bug. Routes and dependencies raise these without knowing anything
about HTTP; the one handler registered on `app` in main.py is the only
place that turns any of them into an actual JSON response. That's the
whole point: no matter which route or dependency raises `AppError` (or any
subclass of it), the shape of the response is decided in exactly one
place, guaranteed identical.

Starlette (which FastAPI's exception handling sits on) matches a raised
exception to a handler by walking its class hierarchy and picking the most
specific one registered - see FastAPI's own Install custom exception
handlers docs (https://fastapi.tiangolo.com/tutorial/handling-errors/#install-custom-exception-handlers).
Registering a handler for `AppError` itself is enough to catch every
subclass below it; no per-exception registration needed.
"""

from fastapi import status


class AppError(Exception):
    """Base for every domain error. `status_code` and `error_code` are set
    per subclass, not per instance - each error type has exactly one HTTP
    status and one stable machine-readable code, the same way every time.
    `detail` is human-readable and free to reword later without breaking a
    client that matches on `error_code` instead of parsing the message."""

    status_code: int
    error_code: str

    def __init__(self, detail: str, *, headers: dict[str, str] | None = None) -> None:
        self.detail = detail
        self.headers = headers
        super().__init__(detail)


class DuplicateEmailError(AppError):
    """Raised by /auth/register when the email is already taken - see
    routers/auth.py's own reasoning for checking this before the insert
    rather than letting the database's unique constraint surface as a raw
    500 IntegrityError."""

    status_code = status.HTTP_400_BAD_REQUEST
    error_code = "duplicate_email"

    def __init__(self) -> None:
        super().__init__("Email already registered")


class InvalidCredentialsError(AppError):
    """Raised by /auth/login for both a nonexistent email and a wrong
    password - the identical error either way, so a stranger can't
    enumerate which registered emails exist by watching which failure
    comes back (same reasoning as before, just centralized now)."""

    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "invalid_credentials"

    def __init__(self) -> None:
        super().__init__("Invalid email or password")


class InvalidTokenError(AppError):
    """Raised by get_current_user for every way a token can fail to prove
    a live session - bad signature, expired, malformed `sub`, or a `sub`
    naming a user that's since been deleted. `WWW-Authenticate: Bearer`
    is carried on the exception itself, not hardcoded in the handler -
    the handler stays generic; only this specific error knows it needs
    that header."""

    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "invalid_token"

    def __init__(self) -> None:
        super().__init__("Invalid or expired token", headers={"WWW-Authenticate": "Bearer"})


class BookmarkNotFoundError(AppError):
    """Raised whenever a bookmark doesn't exist *or* exists but belongs to
    someone else - identical response either way, so a stranger can't
    distinguish "not yours" from "doesn't exist" (routers/bookmarks.py's
    existing reasoning, unchanged - just raised as a domain error now
    instead of an inline HTTPException)."""

    status_code = status.HTTP_404_NOT_FOUND
    error_code = "bookmark_not_found"

    def __init__(self) -> None:
        super().__init__("Bookmark not found")
