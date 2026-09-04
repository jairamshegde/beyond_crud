"""
Phase 6: the point of a single registered handler (see exceptions.py and
main.py's `app_error_handler`) isn't just that each error looks reasonable
individually - it's that every domain error, raised from wherever it's
raised (a route body, a dependency), comes back through the exact same
shape. These tests check that guarantee directly, not just "the status
code is right."
"""

from fastapi.testclient import TestClient


def test_duplicate_email_error_shape(client: TestClient) -> None:
    payload = {"email": "jane@example.com", "password": "correct horse battery staple"}
    client.post("/v1/auth/register", json=payload)

    response = client.post("/v1/auth/register", json=payload)

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Email already registered",
        "error_code": "duplicate_email",
    }


def test_invalid_credentials_error_shape(client: TestClient, registered_user: dict[str, str]) -> None:
    response = client.post(
        "/v1/auth/login", json={"email": registered_user["email"], "password": "wrong"}
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Invalid email or password",
        "error_code": "invalid_credentials",
    }


def test_invalid_token_error_shape_and_header(client: TestClient) -> None:
    """This one's raised from `get_current_user` (dependencies.py), not a
    route body at all - proof the handler doesn't care where `AppError`
    came from. `WWW-Authenticate: Bearer` (RFC 7235) travels on the
    exception itself and still reaches the client through the generic
    handler - see `AppError.headers` in exceptions.py."""
    response = client.get(
        "/v1/users/me", headers={"Authorization": "Bearer not-a-real-token"}
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Invalid or expired token",
        "error_code": "invalid_token",
    }
    assert response.headers["www-authenticate"] == "Bearer"


def test_bookmark_not_found_error_shape(auth_client: TestClient) -> None:
    response = auth_client.get("/v1/bookmarks/999999")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Bookmark not found",
        "error_code": "bookmark_not_found",
    }


def test_every_domain_error_has_the_same_two_keys(
    client: TestClient, auth_client: TestClient, registered_user: dict[str, str]
) -> None:
    """The actual property a shared base class + one handler is supposed
    to guarantee: not just that each error is individually well-formed,
    but that a client can rely on `detail` + `error_code` and nothing
    else, no matter which of these four completely different failures
    it hit."""
    duplicate_email = client.post("/v1/auth/register", json=registered_user)
    bad_login = client.post(
        "/v1/auth/login", json={"email": registered_user["email"], "password": "wrong"}
    )
    bad_token = client.get("/v1/users/me", headers={"Authorization": "Bearer garbage"})
    missing_bookmark = auth_client.get("/v1/bookmarks/999999")

    for response in (duplicate_email, bad_login, bad_token, missing_bookmark):
        assert set(response.json().keys()) == {"detail", "error_code"}
