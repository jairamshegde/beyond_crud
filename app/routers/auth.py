"""
Phase 3: Registration + login routes.

Same shape as bookmarks.py's routes - a plain SQLAlchemy query inline in the
route body, no separate service-layer class. A dedicated service layer
(wrapping these queries in a `UserService`-style class) is a reasonable
pattern once the query logic gets reused across multiple routes or grows
past what reads cleanly inline; this project stays flat for now, consistent
with every other route so far.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException, status

from app.database import get_db
from app.models import User
from app.schemas import Token, UserCreate, UserLogin, UserRead
from app.security import create_access_token, hash_password, verify_password

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


@router.post("/login", response_model=Token)
def login(payload: UserLogin, db: Session = Depends(get_db)) -> Token:
    """Same "Invalid email or password" detail whether the email doesn't
    exist *or* the password is wrong - a distinct "no such email" message
    would let an attacker enumerate which addresses are registered by
    watching which error comes back. One generic 401 either way; only this
    server-side branching (not the response) tells the two cases apart.
    """
    user = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )

    access_token = create_access_token(user.id)
    return Token(access_token=access_token)
