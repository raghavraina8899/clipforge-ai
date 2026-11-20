"""Storage manager: lists everything HookHunt keeps on disk, with sizes, and deletes only items it listed itself
(ids are re-derived from the database/disk on every call, so no arbitrary path can ever be deleted)."""
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from . import config, db, pipeline


def _size(p: Path) -> int:
    try:
        if p.is_symlink():
            return 0
        if p.is_file():
            return p.stat().st_size
        return sum(f.lstat().st_size for f in p.rglob("*") if f.is_file() and not f.is_symlink())  # links (model cache) would count twice
    except OSError:
        return 0


def _active_projects() -> set:
    return {r["project_id"] for r in db.many("SELECT project_id FROM jobs WHERE status IN ('queued','running')") if r["project_id"]}


def items() -> list:
    out: list = []
    active = _active_projects()
    known = set()
    for p in db.many("SELECT * FROM projects ORDER BY created_at DESC"):
        pid = p["id"]
        known.add(pid)
        P = pipeline.paths(pid)
        d = P["dir"]
        busy = pid in active
        grp = f"{p['name'][:60]}"

        def add(kind, label, detail, nbytes, note="", danger=False):
            if nbytes > 0 or kind == "project":
                out.append({"id": f"proj:{pid}:{kind}", "group": grp, "project_id": pid, "kind": kind, "label": label, "detail": detail,
                            "bytes": nbytes, "note": note, "danger": danger, "busy": busy})

        vp = Path(p["video_path"]) if p.get("video_path") else None
        if vp and vp.exists():
            live = p["source_type"] == "live"
            add("source", "Source video", f"{vp.name} ({p['source_type']})", _size(vp),
                "The recording is the ONLY copy of that footage." if live else "Needed to preview, edit or render again. Re-download or re-upload to get it back.", live)
        add("proxy", "Preview copy (720p)", "proxy.mp4", _size(P["proxy"]), "Used by the editor preview. Deleting it disables the preview until the video is imported again.")
        add("preview", "Temporary clip previews", "preview/", _size(d / "preview"), "Small per-clip downloads for the editor. Safe to delete; re-created when you open a clip.")
        add("exports", "Exported clips", "exports/ (MP4, SRT, thumbnails)", _size(P["exports"]), "Your finished videos. Download them first if you still need them.", True)
        tmp = sum(_size(d / n) for n in ("tmp_audio", "work", "thumbs", "audio.wav"))
        add("temp", "Temporary files", "tmp_audio, work, thumbs", tmp, "Safe to delete.")
        add("project", "Whole project", "everything above + clips, transcript, settings", _size(d), "Removes the project completely.", True)
    for d in sorted(config.PROJECTS_DIR.glob("*")):
        if d.is_dir() and d.name not in known:
            out.append({"id": f"orphan:{d.name}", "group": "Leftovers", "project_id": None, "kind": "orphan", "label": f"Orphan folder {d.name}", "detail": "not linked to any project",
                        "bytes": _size(d), "note": "Left behind by a deleted or failed project. Safe to delete.", "danger": False, "busy": False})
    out.append({"id": "global:logs", "group": "App data", "project_id": None, "kind": "logs", "label": "Log files", "detail": "logs/", "bytes": _size(config.LOG_DIR),
                "note": "Safe to delete (clears the history shown in diagnostics).", "danger": False, "busy": False})
    for a in sorted(config.ASSETS_DIR.glob("*")):
        out.append({"id": f"global:asset:{a.name}", "group": "App data", "project_id": None, "kind": "asset", "label": f"Audio file {a.name}", "detail": "music / sound effect you uploaded",
                    "bytes": _size(a), "note": "Clips that use it will render without it.", "danger": False, "busy": False})
    cache = Path.home() / ".cache" / "huggingface" / "hub"
    for m in sorted(cache.glob("models--Systran--faster-whisper-*")) if cache.exists() else []:
        out.append({"id": f"global:model:{m.name}", "group": "Speech models", "project_id": None, "kind": "model", "label": f"Speech model {m.name.split('faster-whisper-')[-1]}", "detail": "downloaded once from Hugging Face",
                    "bytes": _size(m), "note": "Needed for transcription. It downloads again the next time you process a video.", "danger": False, "busy": False})
    for z in sorted(Path(tempfile.gettempdir()).glob("tmp*.zip")):
        out.append({"id": f"global:zip:{z.name}", "group": "Leftovers", "project_id": None, "kind": "zip", "label": f"Unfinished bundle {z.name}", "detail": str(z.parent),
                    "bytes": _size(z), "note": "Left behind by an interrupted bundle download. Safe to delete.", "danger": False, "busy": False})
    return out


def delete(ids: list) -> dict:
    by_id = {i["id"]: i for i in items()}
    freed, done, skipped = 0, [], []
    # delete whole-project items last and skip sub-items of a project that is being removed anyway
    whole = {i.split(":")[1] for i in ids if i.endswith(":project") and i in by_id}
    for iid in ids:
        it = by_id.get(iid)
        if not it:
            skipped.append({"id": iid, "reason": "not found (already deleted?)"})
            continue
        if it["busy"]:
            skipped.append({"id": iid, "reason": "the project is being processed right now"})
            continue
        if it["kind"] != "project" and it.get("project_id") in whole:
            continue
        before = it["bytes"]
        try:
            _delete_one(it)
            freed += before
            done.append(iid)
        except OSError as e:
            skipped.append({"id": iid, "reason": str(e)})
    return {"freed": freed, "deleted": len(done), "skipped": skipped}


def _delete_one(it: dict) -> None:
    kind, pid = it["kind"], it.get("project_id")
    if kind == "source":
        proj = db.one("SELECT * FROM projects WHERE id=?", (pid,))
        if proj and proj.get("video_path"):
            Path(proj["video_path"]).unlink(missing_ok=True)
            db.update("projects", pid, video_path=None, meta={**(proj.get("meta") or {}), "source_deleted": True})
    elif kind == "proxy":
        pipeline.paths(pid)["proxy"].unlink(missing_ok=True)
        db.update("projects", pid, proxy_path=None)
    elif kind == "preview":
        shutil.rmtree(pipeline.paths(pid)["dir"] / "preview", ignore_errors=True)
    elif kind == "exports":
        pipeline.delete_exports(pid)
        shutil.rmtree(pipeline.paths(pid)["exports"], ignore_errors=True)
    elif kind == "temp":
        d = pipeline.paths(pid)["dir"]
        for n in ("tmp_audio", "work", "thumbs"):
            shutil.rmtree(d / n, ignore_errors=True)
        (d / "audio.wav").unlink(missing_ok=True)
    elif kind == "project":
        db.delete("clips", "project_id=?", (pid,))
        db.delete("jobs", "project_id=?", (pid,))
        db.delete("projects", "id=?", (pid,))
        shutil.rmtree(config.PROJECTS_DIR / pid, ignore_errors=True)
    elif kind == "orphan":
        shutil.rmtree(config.PROJECTS_DIR / it["id"].split(":", 1)[1], ignore_errors=True)
    elif kind == "logs":
        for f in config.LOG_DIR.glob("*"):
            f.write_text("") if f.name == "clipforge.log" else f.unlink(missing_ok=True)
    elif kind == "asset":
        (config.ASSETS_DIR / it["id"].split(":", 2)[2]).unlink(missing_ok=True)
    elif kind == "model":
        shutil.rmtree(Path.home() / ".cache" / "huggingface" / "hub" / it["id"].split(":", 2)[2], ignore_errors=True)
    elif kind == "zip":
        (Path(tempfile.gettempdir()) / it["id"].split(":", 2)[2]).unlink(missing_ok=True)


def summary() -> dict:
    its = items()
    usage = shutil.disk_usage(config.DATA_DIR)
    return {"items": its, "total": sum(i["bytes"] for i in its if i["kind"] != "project"), "disk_free": usage.free, "disk_total": usage.total}
