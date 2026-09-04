"""
Phase 6: rate-limit tests for /auth/login and /auth/register - the one
place in this app rate limiting applies at all (see AUTH_RATE_LIMIT in
routers/auth.py). `client`'s own fixture resets `app.state.limiter`
before every test (conftest.py), so each test here starts from a clean
count regardless of what earlier tests did against the same routes.
"""

from fastapi.testclient import TestClient

from app.routers.auth import AUTH_RATE_LIMIT

LIMIT = int(AUTH_RATE_LIMIT.split("/")[0])


def test_first_five_login_attempts_are_not_rate_limited(client: TestClient) -> None:
    """Wrong credentials every time - each attempt is still a genuine 401,
    not a 429. The point here is that a real user mistyping a password a
    few times never sees a rate-limit response - only a script blowing
    past the count would."""
    for _ in range(LIMIT):
        response = client.post(
            "/v1/auth/login", json={"email": "nobody@example.com", "password": "wrong"}
        )
        assert response.status_code == 401


def test_sixth_login_attempt_in_the_same_window_is_rate_limited(client: TestClient) -> None:
    for _ in range(LIMIT):
        client.post("/v1/auth/login", json={"email": "nobody@example.com", "password": "wrong"})

    response = client.post(
        "/v1/auth/login", json={"email": "nobody@example.com", "password": "wrong"}
    )

    assert response.status_code == 429
    assert response.json() == {
        "detail": "Too many requests. Please try again later.",
        "error_code": "rate_limit_exceeded",
    }


def test_register_is_rate_limited_independently_of_login(client: TestClient) -> None:
    """Different route, different key - same IP, but slowapi counts by
    (key, endpoint) by default, not by IP alone. Exhausting register's
    count shouldn't touch login's."""
    for i in range(LIMIT):
        client.post(
            "/v1/auth/register",
            json={"email": f"user{i}@example.com", "password": "correct horse battery staple"},
        )
    rate_limited_register = client.post(
        "/v1/auth/register",
        json={"email": "one-too-many@example.com", "password": "correct horse battery staple"},
    )

    still_works = client.post(
        "/v1/auth/login", json={"email": "nobody@example.com", "password": "wrong"}
    )

    assert rate_limited_register.status_code == 429
    assert still_works.status_code == 401  # not 429 - login's own count is untouched
