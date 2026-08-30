"""
Phase 4 backfill: registration and login shipped in Phase 3 with no tests
at all. These are the first automated checks either endpoint has ever had.
"""

from fastapi.testclient import TestClient


def test_register_returns_user_without_password(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={"email": "jane@example.com", "password": "correct horse battery staple"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "jane@example.com"
    assert "id" in body
    assert "password" not in body
    assert "hashed_password" not in body


def test_register_rejects_duplicate_email(client: TestClient) -> None:
    payload = {"email": "jane@example.com", "password": "correct horse battery staple"}
    first = client.post("/auth/register", json=payload)
    assert first.status_code == 201

    second = client.post("/auth/register", json=payload)

    assert second.status_code == 400


def test_login_succeeds_with_correct_credentials(
    client: TestClient, registered_user: dict[str, str]
) -> None:
    response = client.post("/auth/login", json=registered_user)

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str) and body["access_token"]


def test_login_rejects_wrong_password(client: TestClient, registered_user: dict[str, str]) -> None:
    response = client.post(
        "/auth/login", json={"email": registered_user["email"], "password": "not the password"}
    )

    assert response.status_code == 401


def test_login_rejects_unknown_email(client: TestClient) -> None:
    response = client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": "whatever it is"}
    )

    assert response.status_code == 401


def test_login_failure_shape_is_identical_for_wrong_password_and_unknown_email(
    client: TestClient, registered_user: dict[str, str]
) -> None:
    """Phase 3's whole anti-enumeration point (see auth.py's `login`
    docstring): an attacker probing emails must not be able to tell
    "wrong password" apart from "no such account" by the response shape.
    A test that only checks "login fails with 401" doesn't verify that -
    it takes asserting the *same* status and body for both failure reasons."""
    wrong_password = client.post(
        "/auth/login", json={"email": registered_user["email"], "password": "not the password"}
    )
    unknown_email = client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": "whatever it is"}
    )

    assert wrong_password.status_code == unknown_email.status_code
    assert wrong_password.json() == unknown_email.json()
