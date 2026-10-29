# Prod CORS wiring: browser origins come from WEB_ORIGIN env, never stale hardcodes.
# web (NEXT_PUBLIC_API_URL -> API) and API (WEB_ORIGIN -> web) must match in prod.
import contextlib
import importlib
import os

import apps.api.main as main


@contextlib.contextmanager
def _web_origin(value):
    sentinel = object()
    old = os.environ.get("WEB_ORIGIN", sentinel)
    try:
        if value is None:
            os.environ.pop("WEB_ORIGIN", None)
        else:
            os.environ["WEB_ORIGIN"] = value
        yield importlib.reload(main)
    finally:
        if old is sentinel:
            os.environ.pop("WEB_ORIGIN", None)
        else:
            os.environ["WEB_ORIGIN"] = old
        importlib.reload(main)


def test_dev_defaults_allow_localhost():
    with _web_origin(None) as mod:
        origins = mod._cors_origins()
    assert "http://localhost:3000" in origins
    assert "http://127.0.0.1:3000" in origins


def test_web_origin_env_adds_prod_origin():
    url = "https://fin-spy-web-production.up.railway.app"
    with _web_origin(url) as mod:
        origins = mod._cors_origins()
    assert url in origins


def test_web_origin_supports_comma_list_and_ignores_blanks():
    with _web_origin(" https://a.example , ,https://b.example/ ") as mod:
        origins = mod._cors_origins()
    assert "https://a.example" in origins
    assert "https://b.example" in origins


def test_no_stale_clearmind_origin():
    with _web_origin(None) as mod:
        origins = mod._cors_origins()
    assert all("web-production-ad9d4" not in o for o in origins)


def test_preflight_allows_prod_origin():
    from fastapi.testclient import TestClient

    url = "https://fin-spy-web-production.up.railway.app"
    with _web_origin(url) as mod:
        client = TestClient(mod.app)
        r = client.options(
            "/v1/transactions",
            headers={"Origin": url, "Access-Control-Request-Method": "GET"},
        )
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == url
