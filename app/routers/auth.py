"""
Phase 3: Registration route.

Same shape as bookmarks.py's routes - a plain SQLAlchemy query inline in the
route body, no separate service-layer class. The reference course wraps this
in a `UserService` (`src/auth/service.py`); this project stays flat rather
than introducing a new layer partway through, consistent with every other
route so far.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException, status

from app.database import get_db
from app.models import User
from app.schemas import UserCreate, UserRead
from app.security import hash_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    """`email` is unique at the database level (see models.py), but letting
    that constraint be the only guard means a duplicate signup fails with a
    raw IntegrityError - a 500, not a meaningful 400. Checking first turns
    "already registered" into a proper client error before the insert is
    even attempted.

    `payload.password` (plaintext, only ever exists for the duration of
    this request) is hashed before a `User` is ever constructed - the
    plaintext itself never gets assigned to anything that could accidentally
    be logged, stored, or returned.
    """
    existing = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    user = User(email=payload.email, hashed_password=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
