from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import create_app


@pytest.fixture
def session_factory():
    # One shared in-memory database per test.
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    engine.dispose()


@pytest.fixture
def db(session_factory) -> Iterator[Session]:
    with session_factory() as session:
        yield session


@pytest.fixture
def client(session_factory) -> Iterator[TestClient]:
    app = create_app()

    def override_get_db():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client


def register_and_login(client: TestClient, email: str, password: str = "s3cret-pass") -> dict:
    response = client.post("/auth/register", json={"email": email, "password": password})
    assert response.status_code == 201, response.text
    token = client.post("/auth/token", data={"username": email, "password": password})
    return {"Authorization": f"Bearer {token.json()['access_token']}"}


@pytest.fixture
def auth(client) -> dict:
    return register_and_login(client, "amina@example.com")


@pytest.fixture
def other_auth(client) -> dict:
    return register_and_login(client, "brian@example.com")


@pytest.fixture
def category_id(client, auth) -> int:
    categories = client.get("/categories", headers=auth).json()
    return next(c["id"] for c in categories if c["name"] == "Food")
