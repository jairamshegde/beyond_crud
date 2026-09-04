"""
Phase 6: CORSMiddleware tests.

`settings.cors_origins` starts empty - no real frontend exists for this
project yet (see config.py). Starlette's `CORSMiddleware` checks
`origin in self.allow_origins` live, per request (`is_allowed_origin`),
rather than baking a snapshot at startup - so a fixture here can add one
origin to `settings.cors_origins` for the life of a test and remove it
afterward, the same override-then-restore shape conftest.py's own
`client`/`fake_auth_client` fixtures already use.
"""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.config import settings

TRUSTED_ORIGIN = "http://trusted-frontend.example"
UNTRUSTED_ORIGIN = "http://not-on-the-list.example"


@pytest.fixture()
def trusted_origin() -> Generator[str, None, None]:
    settings.cors_origins.append(TRUSTED_ORIGIN)
    try:
        yield TRUSTED_ORIGIN
    finally:
        settings.cors_origins.remove(TRUSTED_ORIGIN)


def test_trusted_origin_gets_the_cors_header(client: TestClient, trusted_origin: str) -> None:
    response = client.get("/health", headers={"Origin": trusted_origin})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == trusted_origin


def test_untrusted_origin_gets_no_cors_header(client: TestClient, trusted_origin: str) -> None:
    """Same route, a *different* Origin - not on the allowlist even though
    some origin is trusted right now. The server's only job is to not hand
    the header out; the browser is what actually enforces the block on
    the requesting page once the header is missing."""
    response = client.get("/health", headers={"Origin": UNTRUSTED_ORIGIN})

    assert response.status_code == 200  # the request still succeeds server-side
    assert "access-control-allow-origin" not in response.headers


def test_no_configured_origins_means_no_cors_header_by_default(client: TestClient) -> None:
    """Without the `trusted_origin` fixture, `settings.cors_origins` is
    whatever .env/the Settings default leaves it - empty, for this
    project, since no real frontend exists yet. Even a plausible-looking
    cross-origin request gets no CORS header back by default."""
    response = client.get("/health", headers={"Origin": "http://anything.example"})

    assert "access-control-allow-origin" not in response.headers


def test_preflight_for_a_trusted_origin_approves_put(client: TestClient, trusted_origin: str) -> None:
    """A real frontend calling PUT/PATCH/DELETE cross-origin needs its
    preflight OPTIONS approved first - the "scout" request from the
    earlier CORS discussion. CORSMiddleware answers this before the
    request ever reaches the route or its auth dependency."""
    response = client.options(
        "/v1/bookmarks/1",
        headers={"Origin": trusted_origin, "Access-Control-Request-Method": "PUT"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == trusted_origin


def test_preflight_for_an_untrusted_origin_is_rejected(client: TestClient) -> None:
    response = client.options(
        "/v1/bookmarks/1",
        headers={"Origin": UNTRUSTED_ORIGIN, "Access-Control-Request-Method": "PUT"},
    )

    assert response.status_code == 400
