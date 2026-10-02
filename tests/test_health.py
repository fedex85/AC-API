from unittest.mock import MagicMock

from app.api.deps import get_db
from app.main import app


def test_health_ok(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "healthy", "database": "ok"}


def test_health_database_down(client):
    broken = MagicMock()
    broken.execute.side_effect = Exception("sin conexión")

    def override():
        yield broken

    app.dependency_overrides[get_db] = override
    res = client.get("/health")
    assert res.status_code == 503
    assert res.json()["status"] == "unhealthy"


def test_root_is_public(client):
    assert client.get("/").status_code == 200
