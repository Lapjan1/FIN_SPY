# In-process worker startup gate: Railway API shares one disk with the vault, so the
# extraction loop runs as a daemon thread when WORKER_ENABLED=true. Local dev keeps
# the separate `python -m apps.worker.main` process (default off -> no double-run).
import threading

import apps.api.main as main


class FakeThread:
    created = []

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.started = False
        FakeThread.created.append(self)

    def start(self):
        self.started = True


def test_worker_disabled_by_default(monkeypatch):
    monkeypatch.delenv("WORKER_ENABLED", raising=False)
    monkeypatch.setattr(threading, "Thread", FakeThread)
    FakeThread.created.clear()
    assert main._maybe_start_worker() is False
    assert FakeThread.created == []


def test_worker_enabled_starts_single_daemon(monkeypatch):
    monkeypatch.setenv("WORKER_ENABLED", "true")
    monkeypatch.setattr(threading, "Thread", FakeThread)
    FakeThread.created.clear()
    from apps.worker.main import worker_loop

    assert main._maybe_start_worker() is True
    assert len(FakeThread.created) == 1
    t = FakeThread.created[0]
    assert t.started is True
    assert t.kwargs.get("daemon") is True
    assert t.kwargs.get("target") is worker_loop
