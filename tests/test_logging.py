"""
Phase 6: logging tests.

`log_capture` adds its own sink with `enqueue=False`, independent of
whatever the app's own sink is configured with (each `logger.add()` call
sets its own - see logging_config.py) - synchronous, so a message is
guaranteed to already be in `messages` the moment `client.post(...)`
returns, no race.
"""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from loguru import logger


@pytest.fixture()
def log_capture() -> Generator[list[str], None, None]:
    messages: list[str] = []
    handler_id = logger.add(messages.append, level="DEBUG", format="{message}", enqueue=False)
    try:
        yield messages
    finally:
        logger.remove(handler_id)


def test_every_request_logs_method_path_status_and_duration(
    client: TestClient, log_capture: list[str]
) -> None:
    client.get("/health")

    request_lines = [m for m in log_capture if "GET /health" in m]
    assert len(request_lines) == 1
    assert "200" in request_lines[0]
    assert "ms" in request_lines[0]


def test_user_registered_is_logged(client: TestClient, log_capture: list[str]) -> None:
    client.post(
        "/v1/auth/register",
        json={"email": "jane@example.com", "password": "correct horse battery staple"},
    )

    assert any("User registered" in m for m in log_capture)


def test_bookmark_created_is_logged(auth_client: TestClient, log_capture: list[str]) -> None:
    auth_client.post(
        "/v1/bookmarks", json={"title": "FastAPI Docs", "url": "https://fastapi.tiangolo.com"}
    )

    assert any("Bookmark created" in m for m in log_capture)


def test_domain_error_is_logged_with_its_error_code(
    client: TestClient, log_capture: list[str]
) -> None:
    client.post(
        "/v1/auth/login", json={"email": "nobody@example.com", "password": "whatever it is"}
    )

    assert any("invalid_credentials" in m for m in log_capture)


def test_password_never_appears_in_any_log_line(client: TestClient, log_capture: list[str]) -> None:
    password = "correct horse battery staple"
    client.post("/v1/auth/register", json={"email": "jane@example.com", "password": password})
    client.post("/v1/auth/login", json={"email": "jane@example.com", "password": password})

    assert not any(password in m for m in log_capture)


def test_token_never_appears_in_any_log_line(
    client: TestClient, registered_user: dict[str, str], log_capture: list[str]
) -> None:
    login = client.post("/v1/auth/login", json=registered_user)
    token = login.json()["access_token"]
    log_capture.clear()  # only care about what happens *after* the token exists

    client.get("/v1/users/me", headers={"Authorization": f"Bearer {token}"})

    assert not any(token in m for m in log_capture)
