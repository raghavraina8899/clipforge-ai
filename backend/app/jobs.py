"""Background job runner. Progress is persisted so the UI reports only real state."""
import logging
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional

from . import db

log = logging.getLogger("jobs")
_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="job")
_ctxs: dict = {}


class Cancelled(Exception):
    pass


class JobCtx:
    def __init__(self, job_id: str):
        self.id = job_id
        self.cancelled = threading.Event()
        self.procs: list = []  # subprocesses to kill on cancel

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
        db.update("jobs", jid, status="running", stage="Starting")
        try:
            result = fn(ctx)
            db.update("jobs", jid, status="done", progress=100, stage="Done", result=result or {})
        except Cancelled:
            db.update("jobs", jid, status="cancelled", stage="Cancelled", message="Cancelled by user")
        except Exception as e:  # noqa: BLE001 - surfaced to the user verbatim
            log.error("job %s (%s) failed: %s\n%s", jid, kind, e, traceback.format_exc())
            db.update("jobs", jid, status="error", stage="Failed", error=str(e) or e.__class__.__name__)
        finally:
            _ctxs.pop(jid, None)

    _pool.submit(run)
    return jid


def cancel(jid: str) -> bool:
    ctx = _ctxs.get(jid)
    if ctx:
        ctx.cancel()
        return True
    return False


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
