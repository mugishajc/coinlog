from datetime import UTC, datetime, timedelta

import jwt

from app.config import get_settings
from app.security import create_access_token, decode_access_token, hash_password, verify_password


def test_password_hashing_round_trip():
    hashed = hash_password("correct horse")
    assert hashed != "correct horse"
    assert verify_password("correct horse", hashed)
    assert not verify_password("wrong", hashed)


def test_token_round_trip():
    assert decode_access_token(create_access_token("42")) == "42"


def test_expired_token_is_rejected():
    settings = get_settings()
    past = datetime.now(UTC) - timedelta(hours=2)
    token = jwt.encode(
        {"sub": "1", "iat": past, "exp": past + timedelta(minutes=5)},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    assert decode_access_token(token) is None


def test_token_signed_with_other_key_is_rejected():
    token = jwt.encode({"sub": "1"}, "not-the-real-key", algorithm="HS256")
    assert decode_access_token(token) is None


def test_register_returns_user_without_password(client):
    response = client.post(
        "/auth/register",
        json={"email": "New@Example.com", "password": "long-enough", "currency": "rwf"},
    )
    body = response.json()
    assert response.status_code == 201
    assert body["email"] == "new@example.com"
    assert body["currency"] == "RWF"
    assert "password" not in body and "hashed_password" not in body


def test_register_creates_default_categories(client, auth):
    names = {c["name"] for c in client.get("/categories", headers=auth).json()}
    assert {"Food", "Transport", "Housing"} <= names


def test_duplicate_email_conflicts(client, auth):
    response = client.post(
        "/auth/register", json={"email": "AMINA@example.com", "password": "another-pass"}
    )
    assert response.status_code == 409


def test_short_password_is_rejected(client):
    response = client.post("/auth/register", json={"email": "x@example.com", "password": "short"})
    assert response.status_code == 422


def test_login_with_wrong_password(client, auth):
    response = client.post(
        "/auth/token", data={"username": "amina@example.com", "password": "nope-nope"}
    )
    assert response.status_code == 401


def test_me_requires_valid_token(client, auth):
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer junk"}).status_code == 401
    assert client.get("/auth/me", headers=auth).json()["email"] == "amina@example.com"


def test_token_for_deleted_user_is_rejected(client):
    headers = {"Authorization": f"Bearer {create_access_token('9999')}"}
    assert client.get("/auth/me", headers=headers).status_code == 401
