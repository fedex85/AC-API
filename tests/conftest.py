import os

# Variables mínimas ANTES de importar la app (tienen prioridad sobre el .env).
# Los tests usan SQLite en memoria; nunca tocan tu base PostgreSQL.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SECRET_KEY"] = "clave-solo-para-tests"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.api.v1.endpoints.login import login_limiter
from app.crud import user as crud_user
from app.db.base import Base  # registra todos los modelos
from app.main import app
from app.schemas.user import UserCreate

PASSWORD = "contraseña-de-prueba"


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    login_limiter.clear()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    login_limiter.clear()


def make_user(db, email, *, superuser=False, active=True, password=PASSWORD):
    return crud_user.create_user(
        db,
        UserCreate(email=email, password=password),
        is_superuser=superuser,
        is_active=active,
    )


def login(client, email, password=PASSWORD):
    return client.post(
        "/api/v1/login/access-token",
        data={"username": email, "password": password},
    )


def auth_headers(client, email, password=PASSWORD):
    res = login(client, email, password)
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture()
def admin_headers(client, db):
    make_user(db, "admin@example.com", superuser=True)
    return auth_headers(client, "admin@example.com")


@pytest.fixture()
def user_headers(client, db):
    make_user(db, "user@example.com")
    return auth_headers(client, "user@example.com")


def ac_payload(**overrides):
    data = {
        "brand": "Daikin",
        "model": "FTXM35",
        "ac_type": "split",
        "btu_capacity": 12000,
        "power_consumption": 1000,
        "energy_rating": "A++",
        "recommended_area_m2": 30,
        "price": 799.9,
        "has_inverter": True,
        "stock_quantity": 5,
    }
    data.update(overrides)
    return data
