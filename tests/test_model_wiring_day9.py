"""Day-9 model wiring: admin selection -> (provider, model_id) resolution.

Hermetic: env monkeypatching for most paths (no DB touch); the settings-table
path saves + restores table keys; no live model calls anywhere.
"""
import pytest

from apps.worker.llm.client import (
    DEFAULT_MODEL,
    DEFAULT_PROVIDER,
    get_client,
    provider_for_model,
    resolve_model,
)

TABLE_KEYS = ("model_extraction", "model_chat", "model", "model_default")
ENV_KEYS = ("MODEL_EXTRACTION", "MODEL_CHAT", "MODEL", "MODEL_DEFAULT",
            "META_API_KEY", "FREELLMAPI_API_KEY", "OLLAMA_API_KEY")


@pytest.fixture(autouse=True)
def _iso(monkeypatch):
    from apps.api.db import init_db, get_db
    for k in ENV_KEYS:
        monkeypatch.delenv(k, raising=False)
    init_db()
    db = get_db()
    saved = {}
    for k in TABLE_KEYS:
        row = db.execute("SELECT value FROM settings WHERE key=?", (k,)).fetchone()
        if row is None:
            saved[k] = None
        elif isinstance(row, dict):
            saved[k] = row["value"]
        else:
            saved[k] = row[0]
        db.execute("DELETE FROM settings WHERE key=?", (k,))
    db.commit()
    yield
    for k, v in saved.items():
        if v is None:
            db.execute("DELETE FROM settings WHERE key=?", (k,))
        else:
            db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", (k, v))
    db.commit()


def test_default_resolves_dev_proxy():
    assert resolve_model("extraction") == (DEFAULT_PROVIDER, DEFAULT_MODEL)
    assert resolve_model("chat") == (DEFAULT_PROVIDER, DEFAULT_MODEL)


def test_env_model_selects_official(monkeypatch):
    monkeypatch.setenv("MODEL", "muse-spark-1.3")
    assert resolve_model("extraction") == ("meta_official", "muse-spark-1.3")


def test_purpose_override_wins(monkeypatch):
    monkeypatch.setenv("MODEL", "muse-spark-1.3")
    monkeypatch.setenv("MODEL_CHAT", "llama3.2:latest")
    assert resolve_model("chat") == ("ollama", "llama3.2:latest")
    assert resolve_model("extraction") == ("meta_official", "muse-spark-1.3")


def test_contributor_refused_from_selection(monkeypatch):
    monkeypatch.setenv("MODEL", "muse-spark-1.3-contributor")
    assert resolve_model("extraction") == (DEFAULT_PROVIDER, DEFAULT_MODEL)


def test_unknown_model_stays_on_proxy(monkeypatch):
    monkeypatch.setenv("MODEL", "some-future-model")
    assert resolve_model("extraction") == ("freellmapi", "some-future-model")


def test_settings_table_path():
    from apps.api.db import set_setting
    set_setting("model", "muse-spark-1.3")
    assert resolve_model("extraction") == ("meta_official", "muse-spark-1.3")


def test_provider_for_model_map():
    assert provider_for_model("muse-spark-1.3") == "meta_official"
    assert provider_for_model("muse-wonder-1.0") == "meta_official"
    assert provider_for_model("llama3.2:latest") == "ollama"
    assert provider_for_model("muse-spark-1.1") == "freellmapi"
    assert provider_for_model("") == "freellmapi"


def test_get_client_builds_resolved():
    c = get_client("extraction")
    assert (c.provider, c.model_id) == (DEFAULT_PROVIDER, DEFAULT_MODEL)


def _pages():
    return [{"page_no": 1, "width": 100, "height": 100,
             "lines": [{"line_id": "L001", "bbox": [0, 0, 1, 1],
                        "text": "hello", "text_hash": "x"}]}]


def test_llm_fallback_resolves_when_unset():
    from apps.worker.parsers.extractor import llm_fallback, ExtractionResult
    result = llm_fallback(_pages())  # no keys -> mock path, hermetic
    assert isinstance(result, ExtractionResult)
    assert result.rows == []  # P0-A0/Q3: never fabricate rows on failure
    assert result.warnings


def test_llm_fallback_explicit_contributor_honored():
    # Explicit code-passed contributor (synthetic test runs) still works;
    # with no key configured this stays on the mock path - no live call.
    from apps.worker.parsers.extractor import llm_fallback, ExtractionResult
    result = llm_fallback(_pages(), model_id="muse-spark-1.3-contributor")
    assert isinstance(result, ExtractionResult)
