"""
Phase 3: GET /users/me - the simplest possible consumer of get_current_user.

Separate from routers/auth.py on purpose: /auth is about *becoming*
authenticated (register, login); /users/me is about *being* authenticated -
it's the first route in the project that only runs at all once
`get_current_user` has already succeeded.
"""

from fastapi import APIRouter, Depends

from app.dependencies import get_current_user
from app.models import User
from app.schemas import UserRead

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    """No query, no lookup here - `get_current_user` already did the
    `db.get(User, user_id)` fetch as part of verifying the token. This
    route's entire body is "return what the dependency handed you"."""
    return current_user
