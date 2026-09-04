"""
Phase 6: OpenAPI docs tests.

Not testing FastAPI's own schema generation (that's the framework's job,
not this app's) - testing that *this app's* `responses=` declarations
actually match what the routes can really return, since nothing enforces
that by construction (see `ErrorResponse`'s own docstring in schemas.py:
it has to be kept in sync with app_error_handler by hand).
"""

from fastapi.testclient import TestClient


def test_every_tag_has_a_real_description(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()

    tags = {tag["name"]: tag["description"] for tag in schema["tags"]}
    assert set(tags) == {"auth", "bookmarks", "users", "meta"}
    assert all(description for description in tags.values())


def test_bookmark_lookup_routes_document_401_and_404(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    bookmark_by_id = schema["paths"]["/v1/bookmarks/{bookmark_id}"]

    for method in ("get", "put", "patch", "delete"):
        assert {"401", "404"} <= set(bookmark_by_id[method]["responses"])


def test_list_and_create_bookmarks_document_401_but_not_404(client: TestClient) -> None:
    """These two never call `_get_bookmark_or_404` - documenting a 404
    they can't actually return would be as misleading as documenting
    nothing at all."""
    schema = client.get("/openapi.json").json()
    bookmarks_collection = schema["paths"]["/v1/bookmarks"]

    for method in ("get", "post"):
        responses = set(bookmarks_collection[method]["responses"])
        assert "401" in responses
        assert "404" not in responses


def test_register_and_login_document_their_own_distinct_errors(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()

    register_responses = schema["paths"]["/v1/auth/register"]["post"]["responses"]
    login_responses = schema["paths"]["/v1/auth/login"]["post"]["responses"]
    assert "400" in register_responses
    assert "401" in login_responses
    # Phase 6: both are rate-limited (see routers/auth.py's AUTH_RATE_LIMIT) -
    # a 429 nothing else in the app can return.
    assert "429" in register_responses
    assert "429" in login_responses
