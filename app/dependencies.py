"""
Phase 3: get_current_user - the dependency chain from the Phase 3 doc.

Lives in its own module (not inside routers/auth.py) because it's a
cross-cutting dependency - bookmarks.py will depend on it too, once
ownership enforcement lands, same reason get_db lives in database.py
rather than inside any one router.

`HTTPBearer` (not `OAuth2PasswordBearer`) does exactly one job: read the
`Authorization` header, confirm it's shaped like `Bearer <token>`, and hand
back an `HTTPAuthorizationCredentials` object whose `.credentials` is the
token string. It does not decode or verify anything - same
"extracts, doesn't validate" role `OAuth2PasswordBearer` would have played.
`OAuth2PasswordBearer` was deliberately not used here: its Swagger
"Authorize" integration assumes a `tokenUrl` accepting OAuth2's own
form-encoded `username`/`password` fields (see FastAPI's own
[Simple OAuth2](https://fastapi.tiangolo.com/tutorial/security/simple-oauth2/)
docs), and this project's `/auth/login` accepts JSON with an `email` field
instead - `HTTPBearer` just expects a token to paste in, which matches that
shape as-is. Missing header, or a scheme that isn't literally "Bearer" ->
`HTTPBearer` itself raises 401 "Not authenticated" before `get_current_user`
ever runs; a syntactically fine but bogus/expired token is what
`get_current_user` below is responsible for catching.
"""

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.exceptions import InvalidTokenError
from app.models import User
from app.security import decode_access_token

bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """One exception type, raised for every way this can fail - bad
    signature, expired token, a `sub` that isn't a valid int, or a `sub`
    naming a user that's since been deleted. None of these should tell the
    client *which* one happened (same enumeration reasoning as login's
    single 401) - just that whatever they presented isn't currently a
    valid, live session. Phase 6: `InvalidTokenError` (exceptions.py)
    carries its own `WWW-Authenticate: Bearer` header now - this function
    no longer builds the response itself, just raises what happened.
    """
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise InvalidTokenError()

    user = db.get(User, user_id)
    if user is None:
        raise InvalidTokenError()

    return user
