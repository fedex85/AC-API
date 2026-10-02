import re


def test_panel_is_public_and_hardened(client):
    res = client.get("/panel/")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "Catálogo de climatización" in res.text

    csp = res.headers["content-security-policy"]
    assert "script-src 'self'" in csp
    assert "unsafe-inline" not in csp and "unsafe-eval" not in csp
    assert res.headers["x-content-type-options"] == "nosniff"


def test_panel_has_no_inline_scripts_or_handlers(client):
    html = client.get("/panel/").text
    assert not re.search(r"<script(?![^>]*\bsrc=)", html)
    assert not re.search(r"\son[a-z]+\s*=", html)
    assert "panel.js" in html and "panel.css" in html


def test_panel_assets_are_served(client):
    for name in ("panel.js", "panel.css"):
        res = client.get(f"/panel/{name}")
        assert res.status_code == 200
        assert "content-security-policy" in res.headers


def test_panel_without_trailing_slash_redirects(client):
    res = client.get("/panel", follow_redirects=False)
    assert res.status_code in (307, 308)
    assert res.headers["location"].endswith("/panel/")


def test_api_is_not_affected_by_panel_headers(client):
    res = client.get("/health")
    assert "content-security-policy" not in res.headers
