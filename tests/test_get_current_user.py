"""
Phase 4 backfill: `get_current_user` (Phase 3) has never had a test for any
of its failure modes. `GET /users/me` is the simplest possible consumer -
its whole body is "return what the dependency handed you" - so it's the
cleanest route to exercise the dependency itself through.

Every case here is deliberately checked against the identical 401 + detail
(see dependencies.py's docstring): bad signature, expired token, and a
`sub` naming a deleted user are different failures server-side, but none
of them should be distinguishable from the response alone.
"""

from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient

from app.config import settings


def test_users_me_requires_a_token(client: TestClient) -> None:
    response = client.get("/users/me")

    assert response.status_code == 401


def test_users_me_rejects_malformed_token(client: TestClient) -> None:
    client.headers["Authorization"] = "Bearer not-a-real-jwt"

    response = client.get("/users/me")

    assert response.status_code == 401


def test_users_me_rejects_expired_token(client: TestClient, registered_user: dict[str, str]) -> None:
    login = client.post("/auth/login", json=registered_user)
    user_id = client.get(
        "/users/me", headers={"Authorization": f"Bearer {login.json()['access_token']}"}
    ).json()["id"]

    expired_token = jwt.encode(
        {"sub": str(user_id), "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    client.headers["Authorization"] = f"Bearer {expired_token}"

    response = client.get("/users/me")

    assert response.status_code == 401


def test_users_me_rejects_token_for_a_user_that_no_longer_exists(client: TestClient) -> None:
    """A syntactically valid, unexpired token whose `sub` doesn't match any
    row in `users` - e.g. the user was deleted after the token was issued.
    Never actually deleting a user here; a `sub` that was simply never
    assigned (999999) exercises the identical code path."""
    token_for_nobody = jwt.encode(
        {
            "sub": "999999",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    client.headers["Authorization"] = f"Bearer {token_for_nobody}"

    response = client.get("/users/me")

    assert response.status_code == 401


def test_users_me_succeeds_with_a_valid_token(auth_client: TestClient) -> None:
    response = auth_client.get("/users/me")

    assert response.status_code == 200
    assert response.json()["email"] == "jane@example.com"


def test_get_current_users_own_failure_modes_return_the_identical_response(
    client: TestClient, registered_user: dict[str, str]
) -> None:
    """Same anti-enumeration reasoning as auth.py's login - a caller
    presenting a bad-but-present token shouldn't be able to tell *which*
    of these was wrong (bad signature vs. expired vs. deleted user) just
    from the response. Deliberately excludes "no token at all": per
    dependencies.py's own docstring, that case is intercepted earlier by
    `HTTPBearer` itself with a different message ("Not authenticated")
    before `get_current_user` ever runs - a different code path is
    expected to look different; only get_current_user's own failure modes
    are the ones this test's guarantee actually applies to."""
    client.headers["Authorization"] = "Bearer garbage"
    malformed = client.get("/users/me")

    login = client.post("/auth/login", json=registered_user)
    user_id = client.get(
        "/users/me", headers={"Authorization": f"Bearer {login.json()['access_token']}"}
    ).json()["id"]
    expired_token = jwt.encode(
        {"sub": str(user_id), "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    client.headers["Authorization"] = f"Bearer {expired_token}"
    expired = client.get("/users/me")

    token_for_nobody = jwt.encode(
        {"sub": "999999", "exp": datetime.now(timezone.utc) + timedelta(minutes=30)},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    client.headers["Authorization"] = f"Bearer {token_for_nobody}"
    deleted_user = client.get("/users/me")

    assert malformed.status_code == expired.status_code == deleted_user.status_code == 401
    assert malformed.json() == expired.json() == deleted_user.json()
