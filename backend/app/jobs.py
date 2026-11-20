"""Background job runner. Progress is persisted so the UI reports only real state."""
import logging
import threading
import time
import traceback
from typing import Callable, Optional

from . import db

log = logging.getLogger("jobs")
MAX_PARALLEL = 2
_slots = threading.Semaphore(MAX_PARALLEL)  # how many jobs may run at once; waiting jobs are cheap threads that can be cancelled
_ctxs: dict = {}


class Cancelled(Exception):
    pass


class JobCtx:
    def __init__(self, job_id: str):
        self.id = job_id
        self.cancelled = threading.Event()
        self.procs: list = []  # subprocesses to kill on cancel
        self._slot_lock = threading.Lock()
        self._owns_slot = False

    def _take_slot(self):
        with self._slot_lock:
            self._owns_slot = True

    def release_slot(self):
        """Give the run slot back (once). Called when the job ends, or immediately on cancel so a frozen worker cannot block other jobs."""
        with self._slot_lock:
            if self._owns_slot:
                self._owns_slot = False
                _slots.release()

    def update(self, stage: Optional[str] = None, progress: Optional[float] = None, message: Optional[str] = None):
        if self.cancelled.is_set():
            raise Cancelled()
        f = {}
        if stage is not None:
            f["stage"] = stage
        if progress is not None:
            f["progress"] = round(max(0.0, min(100.0, progress)), 1)
        if message is not None:
            f["message"] = message
        db.update("jobs", self.id, **f)

    def check(self):
        if self.cancelled.is_set():
            raise Cancelled()

    def cancel(self):
        self.cancelled.set()
        for p in list(self.procs):
            try:
                p.kill()
            except Exception:
                pass


def submit(kind: str, fn: Callable[[JobCtx], Optional[dict]], project_id=None, clip_id=None) -> str:
    jid = db.new_id()
    db.insert("jobs", dict(id=jid, project_id=project_id, clip_id=clip_id, kind=kind, status="queued",
                           stage="Queued", progress=0, created_at=time.time(), updated_at=time.time()))
    ctx = JobCtx(jid)
    _ctxs[jid] = ctx

    def run():
        try:
            # wait for a free slot; a job cancelled while waiting never starts and never touches its status again
            while not _slots.acquire(timeout=0.4):
                if ctx.cancelled.is_set():
                    return
            ctx._take_slot()
            if ctx.cancelled.is_set():
                return
            db.update("jobs", jid, status="running", stage="Starting")
            try:
                result = fn(ctx)
                if not ctx.cancelled.is_set():
                    db.update("jobs", jid, status="done", progress=100, stage="Done", result=result or {})
            except Cancelled:
                pass  # status was already set to 'cancelled' by cancel()
            except Exception as e:  # noqa: BLE001 - surfaced to the user verbatim
                if not ctx.cancelled.is_set():  # killed on purpose: not a failure
                    log.error("job %s (%s) failed: %s\n%s", jid, kind, e, traceback.format_exc())
                    db.update("jobs", jid, status="error", stage="Failed", error=str(e) or e.__class__.__name__)
        finally:
            ctx.release_slot()
            _ctxs.pop(jid, None)

    threading.Thread(target=run, daemon=True, name=f"job-{kind}-{jid[:6]}").start()
    return jid


def _kill_children(match: str) -> int:
    """Kill direct child processes (e.g. the ffmpeg that yt-dlp starts) whose command line mentions `match`."""
    import os
    import signal
    import subprocess
    n = 0
    out = subprocess.run(["ps", "-A", "-o", "pid=,ppid=,command="], capture_output=True, text=True).stdout
    for line in out.splitlines():
        parts = line.split(None, 2)
        if len(parts) == 3 and parts[1] == str(os.getpid()) and match in parts[2]:
            try:
                os.kill(int(parts[0]), signal.SIGKILL)
                n += 1
            except OSError:
                pass
    return n


def cancel(jid: str, only_queued: bool = False) -> bool:
    """Cancel now: flag the worker, kill hung child processes, free its run slot and show 'cancelled' immediately,
    even if the worker thread is stuck in a network call. Works for queued, running and orphaned ('ghost') jobs."""
    row = db.one("SELECT project_id, kind, status FROM jobs WHERE id=?", (jid,))
    if not row or row["status"] not in ("queued", "running"):
        return False
    if only_queued and row["status"] != "queued":
        return False
    ctx = _ctxs.get(jid)
    if ctx:
        ctx.cancel()
        if row.get("project_id"):
            _kill_children(row["project_id"])
    db.update("jobs", jid, status="cancelled", stage="Cancelled", message="Cancelled by user")
    if ctx:
        ctx.release_slot()
    if row.get("project_id") and row["kind"] in ("ingest", "analyze"):
        p = db.one("SELECT status FROM projects WHERE id=?", (row["project_id"],))
        if p and p["status"] == "processing":
            db.update("projects", row["project_id"], status="error", error="Cancelled. Press Try again to start again.")
    return True


def clean_temp_downloads() -> None:
    """Interrupted jobs can leave temporary downloads behind (they can be GBs): remove them at startup."""
    import shutil
    from .config import PROJECTS_DIR
    for pdir in PROJECTS_DIR.glob("*"):
        ta = pdir / "tmp_audio"
        if ta.exists() and time.time() - ta.stat().st_mtime > 86400:  # keep recent audio so a retry can resume
            shutil.rmtree(ta, ignore_errors=True)
        shutil.rmtree(pdir / "work", ignore_errors=True)
        for part in (pdir / "preview").glob("*.part*") if (pdir / "preview").exists() else []:
            part.unlink(missing_ok=True)


def recover_interrupted() -> None:
    """Jobs left running by a previous process can never finish: mark them failed honestly."""
    for j in db.many("SELECT id FROM jobs WHERE status IN ('queued','running')"):
        db.update("jobs", j["id"], status="error", stage="Failed", error="Interrupted: the server restarted while this job was running.")
    for p in db.many("SELECT id FROM projects WHERE status='processing'"):
        db.update("projects", p["id"], status="error", error="Processing was interrupted by a server restart. Re-run analysis.")
