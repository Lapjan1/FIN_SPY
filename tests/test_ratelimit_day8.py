"""
Day-8 rate limiting: token bucket + per-tenant fairness + retries, all with
injectable clocks (no real sleeping in unit tests).
"""
import pytest

from apps.worker.llm.ratelimit import TokenBucketLimiter, with_retries


class Clock:
    def __init__(self):
        self.t = 1000.0

    def now(self):
        return self.t

    def advance(self, s):
        self.t += s


def test_bucket_allows_burst_then_waits():
    c = Clock()
    lim = TokenBucketLimiter(rpm=2, now_fn=c.now)
    assert lim.acquire("a") == 0.0
    assert lim.acquire("a") == 0.0
    wait = lim.acquire("a")
    assert 25.0 < wait <= 60.0  # global empty or fair share spent
    c.advance(61)
    assert lim.acquire("a") == 0.0  # new window refills


def test_fairness_blocks_hog_not_fresh_tenant():
    c = Clock()
    lim = TokenBucketLimiter(rpm=2, now_fn=c.now)
    assert lim.acquire("hog") == 0.0
    assert lim.acquire("hog") == 0.0  # hog at fair share (2/1 tenant)
    hog_wait = lim.acquire("hog")
    fresh_wait = lim.acquire("fresh")
    assert hog_wait == pytest.approx(60.0)  # fairness: wait for next window
    assert fresh_wait == pytest.approx(30.0)  # global bucket only


def test_refill_over_time():
    c = Clock()
    # drain precisely with fresh tenants to dodge fairness (rpm=60: 1 tok/sec)
    lim2 = TokenBucketLimiter(rpm=60, now_fn=c.now)
    for i in range(60):
        assert lim2.acquire(f"t{i}") == 0.0
    assert lim2.acquire("late") > 0
    c.advance(2)
    assert lim2.acquire("late2") == 0.0  # ~2 tokens refilled


def test_retries_transient_then_succeeds():
    sleeps = []
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise ConnectionError("connection refused")
        return "ok"

    assert with_retries(flaky, sleep_fn=sleeps.append) == "ok"
    assert len(calls) == 3
    assert sleeps == [pytest.approx(0.2), pytest.approx(0.4)]


def test_retries_skip_non_retryable_and_exhaust():
    calls = []

    def bad():
        calls.append(1)
        raise ValueError("bad request 400")

    with pytest.raises(ValueError):
        with_retries(bad, sleep_fn=lambda s: None)
    assert len(calls) == 1

    calls2 = []

    def down():
        calls2.append(1)
        raise TimeoutError("timeout")

    with pytest.raises(TimeoutError):
        with_retries(down, max_retries=2, sleep_fn=lambda s: None)
    assert len(calls2) == 3  # 1 + 2 retries


def test_client_retries_then_succeeds(monkeypatch):
    import apps.worker.llm.client as cli

    attempts = []

    class FakeMsg:
        content = "hello"
        tool_calls = None

    class FakeChoice:
        message = FakeMsg()
        finish_reason = "stop"

    class FakeResp:
        choices = [FakeChoice()]
        usage = None

    class FakeCompletions:
        def create(self, **kw):
            attempts.append(1)
            if len(attempts) < 3:
                raise ConnectionError("connection refused")
            return FakeResp()

    class FakeChat:
        completions = FakeCompletions()

    class FakeOpenAI:
        def __init__(self, base_url=None, api_key=None):
            self.chat = FakeChat()

    import openai
    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)
    monkeypatch.setenv("FREELLMAPI_API_KEY", "test-key")
    client = cli.MetaClient(provider="freellmapi", model_id="muse-spark-1.1")
    res = client.complete([{"role": "user", "content": "hi"}], tenant_id="t1")
    assert res.content == "hello"
    assert len(attempts) == 3


def test_client_returns_mock_when_wait_too_long(monkeypatch):
    import apps.worker.llm.client as cli

    class FullBucket:
        def acquire(self, tenant_id="default"):
            return 999.0

    monkeypatch.setattr("apps.worker.llm.ratelimit.get_limiter", lambda: FullBucket())
    monkeypatch.setenv("FREELLMAPI_API_KEY", "test-key")
    client = cli.MetaClient(provider="freellmapi", model_id="muse-spark-1.1")
    res = client.complete([{"role": "user", "content": "hi"}], tenant_id="t1")
    assert res.usage.get("error") == "rate_limited"
    assert res.usage["wait_s"] == 999.0


def test_llm_fallback_accepts_tenant(monkeypatch):
    from apps.worker.parsers.extractor import llm_fallback

    monkeypatch.delenv("FREELLMAPI_API_KEY", raising=False)
    pages = [{"page_no": 1, "width": 595, "height": 842, "lines": [
        {"line_id": "L001", "bbox": [0, 0, 100, 10], "text": "x", "text_hash": "a"}]}]
    result = llm_fallback(pages, tenant_id="tenant-xyz")
    assert len(result.rows) >= 1
