"""
Phase 4: Testing foundation - fixtures every test file in this suite shares.

The whole point of this file (see the Phase 4 doc's "Dependency Overrides"
section): `get_db` was built as an injectable dependency back in Phase 2
specifically so it could be swapped out later without touching a single
route. This is that payoff.

`db_session` and `client` follow FastAPI's own documented pattern for
testing against a database (https://fastapi.tiangolo.com/advanced/testing-database/):
an in-memory SQLite engine, `StaticPool` so every connection from every
thread sees the *same* in-memory database instead of each getting its own
(and therefore empty) one, tables created fresh before each test and
dropped after - so test order never matters and no test can see another
test's data.
"""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.dependencies import get_current_user
from app.main import app
from app.models import User
from app.security import hash_password

TEST_DATABASE_URL = "sqlite://"  # in-memory, distinct from bookmarks.db

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    """One fresh, empty schema per test - created before, dropped after."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """A `TestClient` wired to the test database instead of the real one.

    Every request made through this client, for the life of one test,
    shares the same `db_session` - matching FastAPI's own documented
    pattern, not a new session per request the way production `get_db`
    behaves. Good enough for testing route behavior; the request-scoped
    session lifecycle itself is what Phase 2/4's other tests already cover
    conceptually.
    """

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def registered_user(client: TestClient) -> dict[str, str]:
    """Registers one real user via the actual endpoint. Returns the
    credentials used, so a test can log in with them."""
    credentials = {"email": "jane@example.com", "password": "correct horse battery staple"}
    response = client.post("/auth/register", json=credentials)
    assert response.status_code == 201
    return credentials


@pytest.fixture()
def auth_client(client: TestClient, registered_user: dict[str, str]) -> TestClient:
    """`client`, but with a real `Authorization` header from an actual
    login - the higher-fidelity option from the Phase 4 doc's "Two Ways to
    Get an Authenticated Request" section. Exercises register -> login ->
    protected-route access end to end, not just a `get_current_user`
    override standing in for it."""
    response = client.post("/auth/login", json=registered_user)
    assert response.status_code == 200
    token = response.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client


@pytest.fixture()
def fake_auth_client(client: TestClient, db_session: Session) -> Generator[TestClient, None, None]:
    """The faster alternative from the Phase 4 doc: skips the real
    register/login/JWT round trip entirely by overriding `get_current_user`
    directly. Right for a test that needs *an* authenticated user to
    exercise something else (e.g. the querying endpoint in Phase 5) and
    isn't itself testing auth - `auth_client` above is still what to reach
    for when the test is actually about auth or wants end-to-end
    confidence that register -> login -> protected access genuinely works
    together.

    Still inserts a real `User` row: routes that touch `current_user.id`
    (every bookmark route does, for ownership scoping) need it to actually
    exist in the test database, not just be a mock object floating in
    memory.
    """
    user = User(email="fake@example.com", hashed_password=hash_password("unused"))
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    app.dependency_overrides[get_current_user] = lambda: user
    try:
        yield client
    finally:
        del app.dependency_overrides[get_current_user]
