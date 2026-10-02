from app.core.config import settings
from tests.conftest import PASSWORD, auth_headers, login, make_user

API = settings.API_V1_PREFIX


def test_register_forces_normal_user(client):
    res = client.post(
        f"{API}/users/",
        json={
            "email": "nuevo@example.com",
            "password": PASSWORD,
            "full_name": "Nuevo",
            "is_superuser": True,  # debe ignorarse
            "is_active": False,  # debe ignorarse
        },
    )
    assert res.status_code == 201
    body = res.json()
    assert body["email"] == "nuevo@example.com"
    assert body["is_superuser"] is False
    assert body["is_active"] is True
    assert "password" not in body and "hashed_password" not in body


def test_register_duplicate_email(client, db):
    make_user(db, "dup@example.com")
    res = client.post(
        f"{API}/users/", json={"email": "dup@example.com", "password": PASSWORD}
    )
    assert res.status_code == 400


def test_register_short_password(client):
    res = client.post(
        f"{API}/users/", json={"email": "a@example.com", "password": "123"}
    )
    assert res.status_code == 422


def test_login_ok_and_me(client, db):
    make_user(db, "ana@example.com")
    headers = auth_headers(client, "ana@example.com")
    res = client.get(f"{API}/users/me", headers=headers)
    assert res.status_code == 200
    assert res.json()["email"] == "ana@example.com"


def test_login_wrong_password_and_unknown_user_same_message(client, db):
    make_user(db, "ana@example.com")
    r1 = login(client, "ana@example.com", "incorrecta-123")
    r2 = login(client, "noexiste@example.com", "incorrecta-123")
    assert r1.status_code == r2.status_code == 401
    assert r1.json()["detail"] == r2.json()["detail"]


def test_me_requires_token(client):
    assert client.get(f"{API}/users/me").status_code == 401


def test_me_rejects_invalid_token(client):
    res = client.get(
        f"{API}/users/me", headers={"Authorization": "Bearer token-falso"}
    )
    assert res.status_code == 401


def test_inactive_user_cannot_login(client, db):
    make_user(db, "baja@example.com", active=False)
    assert login(client, "baja@example.com").status_code == 400


def test_user_cannot_read_other_user(client, db):
    make_user(db, "a@example.com")
    other = make_user(db, "b@example.com")
    headers = auth_headers(client, "a@example.com")
    assert client.get(f"{API}/users/{other.id}", headers=headers).status_code == 403


def test_superuser_can_read_other_user(client, db):
    make_user(db, "root@example.com", superuser=True)
    other = make_user(db, "b@example.com")
    headers = auth_headers(client, "root@example.com")
    assert client.get(f"{API}/users/{other.id}", headers=headers).status_code == 200


def test_login_rate_limit(client, db):
    make_user(db, "ana@example.com")
    for _ in range(settings.LOGIN_MAX_ATTEMPTS):
        assert login(client, "ana@example.com", "incorrecta-123").status_code == 401
    # Superado el límite, incluso la contraseña correcta queda bloqueada
    res = login(client, "ana@example.com")
    assert res.status_code == 429
    assert "Retry-After" in res.headers
