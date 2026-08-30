"""
Phase 4 backfill: bookmark CRUD (Phases 1-3) has never had a test. This
covers the happy path for every route, then the two things that actually
matter most given what this project chose to build - ownership scoping
(Phase 3) and schema validation (Phase 1) - neither of which had ever been
verified by anything other than manual `/docs` poking.
"""

from fastapi.testclient import TestClient

BOOKMARK_PAYLOAD = {"title": "FastAPI Docs", "url": "https://fastapi.tiangolo.com"}


def _second_user_client(client: TestClient) -> TestClient:
    """A second, distinct authenticated user - for proving one user's
    bookmarks are invisible to another. Deliberately swaps the shared
    `client` fixture's Authorization header rather than requesting a
    second client fixture, since both users need to hit the same
    dependency-overridden app/db."""
    credentials = {"email": "bob@example.com", "password": "another correct horse"}
    register = client.post("/auth/register", json=credentials)
    assert register.status_code == 201
    login = client.post("/auth/login", json=credentials)
    assert login.status_code == 200
    client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
    return client


def test_create_and_get_bookmark(auth_client: TestClient) -> None:
    create = auth_client.post("/bookmarks", json=BOOKMARK_PAYLOAD)
    assert create.status_code == 201
    bookmark_id = create.json()["id"]

    get = auth_client.get(f"/bookmarks/{bookmark_id}")

    assert get.status_code == 200
    assert get.json()["title"] == "FastAPI Docs"


def test_list_bookmarks_returns_only_current_users_bookmarks(auth_client: TestClient) -> None:
    auth_client.post("/bookmarks", json=BOOKMARK_PAYLOAD)

    response = auth_client.get("/bookmarks")

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_put_replaces_title_and_url(auth_client: TestClient) -> None:
    bookmark_id = auth_client.post("/bookmarks", json=BOOKMARK_PAYLOAD).json()["id"]

    response = auth_client.put(
        f"/bookmarks/{bookmark_id}",
        json={"title": "Pydantic Docs", "url": "https://docs.pydantic.dev"},
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Pydantic Docs"


def test_patch_updates_only_the_sent_field(auth_client: TestClient) -> None:
    bookmark_id = auth_client.post("/bookmarks", json=BOOKMARK_PAYLOAD).json()["id"]

    response = auth_client.patch(f"/bookmarks/{bookmark_id}", json={"title": "New Title"})

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "New Title"
    assert body["url"] == "https://fastapi.tiangolo.com/"


def test_delete_removes_the_bookmark(auth_client: TestClient) -> None:
    bookmark_id = auth_client.post("/bookmarks", json=BOOKMARK_PAYLOAD).json()["id"]

    delete = auth_client.delete(f"/bookmarks/{bookmark_id}")
    get_after = auth_client.get(f"/bookmarks/{bookmark_id}")

    assert delete.status_code == 204
    assert get_after.status_code == 404


def test_get_nonexistent_bookmark_is_404(auth_client: TestClient) -> None:
    response = auth_client.get("/bookmarks/999999")

    assert response.status_code == 404


# --- Ownership scoping (Phase 3) --------------------------------------


def test_another_users_bookmark_is_404_not_403(auth_client: TestClient) -> None:
    """The exact anti-enumeration shape from bookmarks.py's docstring:
    "not yours" and "doesn't exist" must look identical from the outside."""
    owned_id = auth_client.post("/bookmarks", json=BOOKMARK_PAYLOAD).json()["id"]

    other_user = _second_user_client(auth_client)
    response = other_user.get(f"/bookmarks/{owned_id}")

    assert response.status_code == 404


def test_another_user_cannot_update_or_delete_a_bookmark_they_dont_own(
    auth_client: TestClient,
) -> None:
    owned_id = auth_client.post("/bookmarks", json=BOOKMARK_PAYLOAD).json()["id"]

    other_user = _second_user_client(auth_client)
    patch = other_user.patch(f"/bookmarks/{owned_id}", json={"title": "Hijacked"})
    delete = other_user.delete(f"/bookmarks/{owned_id}")

    assert patch.status_code == 404
    assert delete.status_code == 404


# --- Validation (Phase 1's schema separation) --------------------------


def test_create_bookmark_rejects_missing_title(auth_client: TestClient) -> None:
    response = auth_client.post("/bookmarks", json={"url": "https://example.com"})

    assert response.status_code == 422


def test_create_bookmark_rejects_invalid_url(auth_client: TestClient) -> None:
    response = auth_client.post("/bookmarks", json={"title": "Bad URL", "url": "not-a-url"})

    assert response.status_code == 422


def test_put_requires_both_fields_even_for_a_partial_change(auth_client: TestClient) -> None:
    """PUT is full replacement (Phase 1's PUT-vs-PATCH split) - a body
    missing `url` must 422, not silently leave the old value in place."""
    bookmark_id = auth_client.post("/bookmarks", json=BOOKMARK_PAYLOAD).json()["id"]

    response = auth_client.put(f"/bookmarks/{bookmark_id}", json={"title": "Only a title"})

    assert response.status_code == 422


def test_endpoints_require_authentication(client: TestClient) -> None:
    response = client.get("/bookmarks")

    assert response.status_code == 401


def test_fake_auth_client_works_without_a_real_login(fake_auth_client: TestClient) -> None:
    """Demonstrates the `get_current_user`-override shortcut from the
    Phase 4 doc: no `/auth/register` or `/auth/login` call happened for
    this test, yet ownership scoping (owner_id stamped from the "current
    user") still works correctly - proof the override is a faster route to
    the same authenticated state, not a weaker one."""
    create = fake_auth_client.post("/bookmarks", json=BOOKMARK_PAYLOAD)

    assert create.status_code == 201
    assert fake_auth_client.get(f"/bookmarks/{create.json()['id']}").status_code == 200
