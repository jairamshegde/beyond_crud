"""
Phase 3: Password hashing + JWT access tokens.

## Password hashing

A thin wrapper around passlib's `CryptContext`, scoped to Argon2 (specifically
Argon2id - passlib/argon2-cffi's default) instead of the reference course's
bcrypt (see `8-User Account Creation...txt` and `src/auth/utils.py` for the
bcrypt version this is patterned on) - a deliberate divergence, not an
oversight; see the Phase 3 doc's hashing notes for why Argon2's memory-hard
cost model is the stronger current default.

`CryptContext` does three things `hash_password`/`verify_password` just
delegate to:
  1. Generates a fresh random salt per call and bakes it into the output
     string - `hash_password("same password")` twice never returns the same
     string twice.
  2. Encodes the algorithm + cost parameters (memory/time/parallelism) into
     that same string, so `verify` can redo the exact same computation
     later without needing those parameters stored anywhere separately.
  3. `deprecated="auto"` means: if this context's *current* params ever
     change (e.g. memory_cost raised later), a hash produced under the old
     params still verifies correctly - `CryptContext.needs_update(hash)`
     is how you'd detect and silently re-hash it on next successful login.
     Not wired up yet - noted for when it's needed.

## JWT access tokens

`create_access_token` mirrors `src/auth/utils.py`'s `create_access_token`
(transcript #9) with PyJWT instead of the fields this project doesn't need
yet (no refresh/jti/blocklist - those are later transcripts, not this
phase's scope). `sub` is the user's id, stored as a *string* - the JWT spec
expects string claims, and PyJWT will silently accept an int here, but
other libraries reading the same token may not. `exp` is computed here, in
UTC, from `settings.access_token_expire_minutes` - PyJWT reads this claim
back out on decode and rejects an expired token on its own, no manual
comparison needed later.
"""

from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return pwd_context.verify(password, hashed_password)


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
