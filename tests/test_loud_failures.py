"""Loud failures: a dead LLM key or a zero-row extraction must never
pass silent. A rejected key raises (not mock), and zero rows can never
be 'proposed' - there is nothing to review."""

import sys
import types

import pytest

from apps.worker.llm.client import MetaClient, ModelAuthError
from apps.worker.main import decide_doc_status


def _pages(*texts):
    return [{"page_no": 1, "lines": [
        {"line_id": f"L{i + 1:03d}", "text": t, "bbox": [0, 0, 100, 10]}
        for i, t in enumerate(texts)]}]


class _FakeAuthError(Exception):
    def __init__(self):
        super().__init__("Error code: 401 - invalid api key")
        self.status_code = 401


def _install_fake_openai(exc, monkeypatch):
    mod = types.ModuleType("openai")

    class _Completions:
        def create(self, **kw):
            raise exc

    class _Chat:
        completions = _Completions()

    class _OpenAI:
        def __init__(self, **kw):
            self.chat = _Chat()

    mod.OpenAI = _OpenAI
    monkeypatch.setitem(sys.modules, "openai", mod)


def test_401_raises_model_auth_error(monkeypatch):
    monkeypatch.setenv("META_API_KEY", "sk-test-not-a-real-key")
    _install_fake_openai(_FakeAuthError(), monkeypatch)
    client = MetaClient(provider="meta_official", model_id="muse-spark-1.3")
    with pytest.raises(ModelAuthError) as ei:
        client.complete([{"role": "user", "content": "hi"}])
    assert "401" in str(ei.value)
    assert "muse-spark-1.3" in str(ei.value)
    assert "sk-test" not in str(ei.value)  # never echo key material


def test_non_auth_error_still_mock(monkeypatch):
    monkeypatch.setenv("FREELLMAPI_API_KEY", "x")
    _install_fake_openai(RuntimeError("socket closed"), monkeypatch)
    client = MetaClient(provider="freellmapi", model_id="muse-spark-1.1")
    res = client.complete([{"role": "user", "content": "hi"}])
    assert "mock" in res.content.lower()
    assert res.usage.get("error")


def test_llm_fallback_propagates_auth_error(monkeypatch):
    from apps.worker.parsers import extractor as X

    class _Boom:
        def __init__(self, provider=None, model_id=None):
            pass

        def complete(self, *a, **k):
            raise ModelAuthError("401 no")

    monkeypatch.setattr(X, "MetaClient", _Boom)
    with pytest.raises(ModelAuthError):
        X.llm_fallback(_pages("29 Oct 2026 VODACOM R300,00 R20 790,55"),
                       model_id="muse-spark-1.1")


def test_zero_rows_never_proposed():
    assert decide_doc_status(True, 0) == "exception"


def test_gate_fail_is_exception():
    assert decide_doc_status(False, 5) == "exception"


def test_rows_and_pass_is_proposed():
    assert decide_doc_status(True, 5) == "proposed"
