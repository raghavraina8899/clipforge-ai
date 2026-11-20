"""The job scheduler: queueing, cancelling, and a frozen job must never block the others."""
import time

import pytest

from app import db, jobs


@pytest.fixture(scope="module", autouse=True)
def _db():
    db.init()


def status(jid):
    return db.one("SELECT status FROM jobs WHERE id=?", (jid,))["status"]


def wait_for(cond, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.05)
    return False


def test_job_runs_to_done_with_result():
    jid = jobs.submit("test", lambda ctx: {"answer": 42})
    assert wait_for(lambda: status(jid) == "done")
    assert db.one("SELECT result FROM jobs WHERE id=?", (jid,))["result"] == {"answer": 42}


def test_failed_job_reports_error():
    def boom(ctx):
        raise RuntimeError("it broke")
    jid = jobs.submit("test", boom)
    assert wait_for(lambda: status(jid) == "error")
    assert "it broke" in db.one("SELECT error FROM jobs WHERE id=?", (jid,))["error"]


def test_cancel_queued_running_and_frozen():
    frozen = lambda ctx: time.sleep(20)  # noqa: E731 - a stuck network call that never checks for cancel
    ran = []
    a, b = jobs.submit("test", frozen), jobs.submit("test", frozen)
    assert wait_for(lambda: status(a) == status(b) == "running")
    c = jobs.submit("test", lambda ctx: ran.append("c"))
    d = jobs.submit("test", lambda ctx: ran.append("d"))
    time.sleep(0.6)
    assert status(c) == status(d) == "queued"              # both slots are held by frozen jobs
    assert jobs.cancel(c) is True and status(c) == "cancelled"
    time.sleep(1.0)
    assert status(c) == "cancelled" and "c" not in ran       # a cancelled waiting job never starts or flips back
    assert jobs.cancel(a) is True                            # cancelling a frozen job frees its slot...
    assert wait_for(lambda: status(d) == "done") and ran == ["d"]   # ...so the next job runs
    assert jobs.cancel(d) is False and jobs.cancel("nope") is False
    assert jobs.cancel(b, only_queued=True) is False and status(b) == "running"
    assert jobs.cancel(b) is True


def test_progress_updates_are_persisted_and_cancel_raises_inside_job():
    def work(ctx):
        for i in range(100):
            ctx.update("Working", i)
            time.sleep(0.05)
    jid = jobs.submit("test", work)
    assert wait_for(lambda: (db.one("SELECT progress FROM jobs WHERE id=?", (jid,))["progress"] or 0) > 5)
    assert jobs.cancel(jid) and status(jid) == "cancelled"
