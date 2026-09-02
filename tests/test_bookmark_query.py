"""
Phase 5: tests for the new querying surface on `GET /bookmarks` - filters,
search, sort, and pagination - written alongside the endpoint itself
(the Phase 4 doc's whole point), reusing `fake_auth_client` since none of
these tests are about auth, just an authenticated user's own bookmarks
(the exact case `fake_auth_client`'s own docstring calls out).
"""

import time

from fastapi.testclient import TestClient


def _create(
    client: TestClient,
    title: str,
    category: str | None = None,
    description: str | None = None,
) -> dict:
    payload = {"title": title, "url": "https://example.com", "category": category, "description": description}
    response = client.post("/bookmarks", json=payload)
    assert response.status_code == 201
    return response.json()


# --- Filtering -----------------------------------------------------------


def test_category_filter_returns_only_matching_bookmarks(fake_auth_client: TestClient) -> None:
    _create(fake_auth_client, "FastAPI Docs", category="docs")
    _create(fake_auth_client, "Kitten Video", category="fun")

    response = fake_auth_client.get("/bookmarks", params={"category": "docs"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "FastAPI Docs"


def test_search_matches_title(fake_auth_client: TestClient) -> None:
    _create(fake_auth_client, "FastAPI Docs")
    _create(fake_auth_client, "Kitten Video")

    response = fake_auth_client.get("/bookmarks", params={"search": "fastapi"})

    assert response.json()["total"] == 1
    assert response.json()["items"][0]["title"] == "FastAPI Docs"


def test_search_matches_description_not_just_title(fake_auth_client: TestClient) -> None:
    """The `search` param's whole reason for covering two columns instead
    of one - a hit that only exists in `description` still has to surface."""
    _create(fake_auth_client, "Untitled Link", description="A guide to async Python")
    _create(fake_auth_client, "Kitten Video")

    response = fake_auth_client.get("/bookmarks", params={"search": "async"})

    assert response.json()["total"] == 1
    assert response.json()["items"][0]["title"] == "Untitled Link"


def test_category_and_search_combine_as_and_not_or(fake_auth_client: TestClient) -> None:
    _create(fake_auth_client, "FastAPI Docs", category="docs")
    _create(fake_auth_client, "FastAPI Tutorial", category="video")

    response = fake_auth_client.get("/bookmarks", params={"category": "docs", "search": "fastapi"})

    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "FastAPI Docs"


# --- Sorting ---------------------------------------------------------------


def test_sort_by_title_ascending(fake_auth_client: TestClient) -> None:
    for title in ("Banana", "Apple", "Cherry"):
        _create(fake_auth_client, title)

    response = fake_auth_client.get("/bookmarks", params={"sort_by": "title", "order": "asc"})

    titles = [item["title"] for item in response.json()["items"]]
    assert titles == ["Apple", "Banana", "Cherry"]


def test_sort_by_title_descending(fake_auth_client: TestClient) -> None:
    for title in ("Banana", "Apple", "Cherry"):
        _create(fake_auth_client, title)

    response = fake_auth_client.get("/bookmarks", params={"sort_by": "title", "order": "desc"})

    titles = [item["title"] for item in response.json()["items"]]
    assert titles == ["Cherry", "Banana", "Apple"]


def test_sort_by_created_at_reflects_insertion_order(fake_auth_client: TestClient) -> None:
    # A tiny sleep guarantees distinct timestamps regardless of clock
    # resolution - without it the test's own correctness would depend on
    # wall-clock granularity, not on the endpoint's behavior.
    for title in ("First", "Second", "Third"):
        _create(fake_auth_client, title)
        time.sleep(0.001)

    response = fake_auth_client.get("/bookmarks", params={"sort_by": "created_at", "order": "asc"})

    titles = [item["title"] for item in response.json()["items"]]
    assert titles == ["First", "Second", "Third"]


def test_unrecognized_sort_by_returns_422(fake_auth_client: TestClient) -> None:
    """The allowlist from the door, not just the lookup table: `sort_by`
    outside {created_at, title} never reaches the handler at all."""
    response = fake_auth_client.get("/bookmarks", params={"sort_by": "owner_id"})

    assert response.status_code == 422


# --- Pagination --------------------------------------------------------


def test_pagination_returns_requested_page_size(fake_auth_client: TestClient) -> None:
    for i in range(5):
        _create(fake_auth_client, f"Bookmark {i}")

    response = fake_auth_client.get("/bookmarks", params={"page": 1, "size": 2})

    body = response.json()
    assert len(body["items"]) == 2
    assert body["total"] == 5
    assert body["total_pages"] == 3


def test_page_past_the_last_page_returns_empty_items_but_correct_total(fake_auth_client: TestClient) -> None:
    _create(fake_auth_client, "Only One")

    response = fake_auth_client.get("/bookmarks", params={"page": 5, "size": 20})

    body = response.json()
    assert response.status_code == 200
    assert body["items"] == []
    assert body["total"] == 1
    assert body["total_pages"] == 1


def test_size_at_the_cap_succeeds(fake_auth_client: TestClient) -> None:
    response = fake_auth_client.get("/bookmarks", params={"size": 100})

    assert response.status_code == 200


def test_size_past_the_cap_returns_422(fake_auth_client: TestClient) -> None:
    response = fake_auth_client.get("/bookmarks", params={"size": 101})

    assert response.status_code == 422


def test_page_zero_returns_422(fake_auth_client: TestClient) -> None:
    response = fake_auth_client.get("/bookmarks", params={"page": 0})

    assert response.status_code == 422


def test_no_bookmarks_gives_zero_total_pages_not_a_division_error(fake_auth_client: TestClient) -> None:
    response = fake_auth_client.get("/bookmarks")

    body = response.json()
    assert body["total"] == 0
    assert body["total_pages"] == 0
    assert body["items"] == []
