"""
Phase 3: get_current_user - the dependency chain from the Phase 3 doc.

Lives in its own module (not inside routers/auth.py) because it's a
cross-cutting dependency - bookmarks.py will depend on it too, once
ownership enforcement lands, same reason get_db lives in database.py
rather than inside any one router.

`HTTPBearer` (not `OAuth2PasswordBearer` - see the chat for why) does
exactly one job: read the `Authorization` header, confirm it's shaped like
`Bearer <token>`, and hand back an `HTTPAuthorizationCredentials` object
whose `.credentials` is the token string. It does not decode or verify
anything - same "extracts, doesn't validate" role OAuth2PasswordBearer
would have played, just matched to how this project's tokens are actually
obtained (see transcript #10's own `HTTPBearer` usage). Missing header, or
a scheme that isn't literally "Bearer" -> `HTTPBearer` itself raises 401
"Not authenticated" before `get_current_user` ever runs; a syntactically
fine but bogus/expired token is what `get_current_user` below is
responsible for catching.
"""

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.security import decode_access_token

bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """One exception, reused for every way this can fail - bad signature,
    expired token, a `sub` that isn't a valid int, or a `sub` naming a user
    that's since been deleted. None of these should tell the client *which*
    one happened (same enumeration reasoning as login's single 401) - just
    that whatever they presented isn't currently a valid, live session.
    """
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise unauthorized

    user = db.get(User, user_id)
    if user is None:
        raise unauthorized

    return user
