from app.core.config import settings
from tests.conftest import ac_payload

URL = f"{settings.API_V1_PREFIX}/air-conditioners/"


def test_all_endpoints_require_login(client):
    assert client.get(URL).status_code == 401
    assert client.get(f"{URL}1").status_code == 401
    assert client.post(URL, json=ac_payload()).status_code == 401
    assert client.patch(f"{URL}1", json={"price": 1}).status_code == 401
    assert client.delete(f"{URL}1").status_code == 401


def test_normal_user_can_read_but_not_write(client, user_headers, admin_headers):
    created = client.post(URL, json=ac_payload(), headers=admin_headers)
    assert created.status_code == 201
    ac_id = created.json()["id"]

    assert client.get(URL, headers=user_headers).status_code == 200
    assert client.get(f"{URL}{ac_id}", headers=user_headers).status_code == 200
    assert client.post(URL, json=ac_payload(), headers=user_headers).status_code == 403
    assert (
        client.patch(f"{URL}{ac_id}", json={"price": 1}, headers=user_headers).status_code
        == 403
    )
    assert client.delete(f"{URL}{ac_id}", headers=user_headers).status_code == 403


def test_superuser_crud_flow(client, admin_headers):
    res = client.post(URL, json=ac_payload(), headers=admin_headers)
    assert res.status_code == 201
    ac = res.json()
    assert ac["brand"] == "Daikin" and ac["id"]

    assert client.get(f"{URL}{ac['id']}", headers=admin_headers).status_code == 200
    assert client.get(f"{URL}9999", headers=admin_headers).status_code == 404

    assert client.delete(f"{URL}{ac['id']}", headers=admin_headers).status_code == 204
    assert client.get(f"{URL}{ac['id']}", headers=admin_headers).status_code == 404
    assert client.delete(f"{URL}{ac['id']}", headers=admin_headers).status_code == 404


def test_create_validation(client, admin_headers):
    res = client.post(URL, json=ac_payload(price=-5), headers=admin_headers)
    assert res.status_code == 422
    res = client.post(URL, json=ac_payload(ac_type="inexistente"), headers=admin_headers)
    assert res.status_code == 422


def test_patch_is_partial(client, admin_headers):
    ac = client.post(URL, json=ac_payload(), headers=admin_headers).json()
    res = client.patch(
        f"{URL}{ac['id']}", json={"price": 650.5}, headers=admin_headers
    )
    assert res.status_code == 200
    body = res.json()
    assert body["price"] == 650.5
    assert body["brand"] == "Daikin"  # no enviado: se conserva
    assert body["btu_capacity"] == 12000


def test_patch_null_on_required_field_is_ignored(client, admin_headers):
    ac = client.post(URL, json=ac_payload(), headers=admin_headers).json()
    res = client.patch(f"{URL}{ac['id']}", json={"brand": None}, headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["brand"] == "Daikin"


def test_patch_not_found(client, admin_headers):
    res = client.patch(f"{URL}9999", json={"price": 1}, headers=admin_headers)
    assert res.status_code == 404


def _seed(client, headers):
    items = [
        ac_payload(brand="Daikin", model="A1", ac_type="split", btu_capacity=9000, price=500, stock_quantity=3),
        ac_payload(brand="LG", model="B2", ac_type="portable", btu_capacity=12000, price=300, stock_quantity=0),
        ac_payload(brand="Samsung", model="C3", ac_type="split", btu_capacity=18000, price=900, stock_quantity=2),
        ac_payload(brand="100%Cool", model="D4", ac_type="window", btu_capacity=7000, price=200, stock_quantity=1, is_available=False),
    ]
    for it in items:
        assert client.post(URL, json=it, headers=headers).status_code == 201


def test_list_pagination_and_total(client, admin_headers):
    _seed(client, admin_headers)
    res = client.get(URL, params={"limit": 2, "skip": 1}, headers=admin_headers)
    body = res.json()
    assert res.status_code == 200
    assert body["total"] == 4 and body["limit"] == 2 and body["skip"] == 1
    assert len(body["items"]) == 2


def test_filter_by_type_and_btu_range(client, admin_headers):
    _seed(client, admin_headers)
    res = client.get(URL, params={"ac_type": "split"}, headers=admin_headers).json()
    assert res["total"] == 2
    res = client.get(
        URL, params={"min_btu": 10000, "max_btu": 15000}, headers=admin_headers
    ).json()
    assert [i["brand"] for i in res["items"]] == ["LG"]


def test_filter_available(client, admin_headers):
    _seed(client, admin_headers)
    res = client.get(URL, params={"available": True}, headers=admin_headers).json()
    assert sorted(i["brand"] for i in res["items"]) == ["Daikin", "Samsung"]
    res = client.get(URL, params={"available": False}, headers=admin_headers).json()
    assert sorted(i["brand"] for i in res["items"]) == ["100%Cool", "LG"]


def test_filter_brand_and_wildcards_are_literal(client, admin_headers):
    _seed(client, admin_headers)
    res = client.get(URL, params={"brand": "dai"}, headers=admin_headers).json()
    assert [i["brand"] for i in res["items"]] == ["Daikin"]
    # '%' se busca literalmente (no como comodín que devuelve todo)
    res = client.get(URL, params={"brand": "%"}, headers=admin_headers).json()
    assert [i["brand"] for i in res["items"]] == ["100%Cool"]


def test_sorting(client, admin_headers):
    _seed(client, admin_headers)
    res = client.get(
        URL, params={"sort_by": "price", "order": "desc"}, headers=admin_headers
    ).json()
    assert [i["price"] for i in res["items"]] == [900, 500, 300, 200]


def test_invalid_ranges_return_400(client, admin_headers):
    res = client.get(URL, params={"min_btu": 20, "max_btu": 10}, headers=admin_headers)
    assert res.status_code == 400
    res = client.get(URL, params={"min_price": 20, "max_price": 10}, headers=admin_headers)
    assert res.status_code == 400


def test_invalid_sort_field_returns_422(client, admin_headers):
    res = client.get(URL, params={"sort_by": "hashed_password"}, headers=admin_headers)
    assert res.status_code == 422
