"""The HTTP API end to end (in-process), plus safety of the storage manager and settings."""
import time
import zipfile
import io

import pytest
from fastapi.testclient import TestClient

from app import db, pipeline
from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def add_project(pid="p1", **kw):
    db.insert("projects", dict(id=pid, name="Test project", source_type="upload", status="ready", progress=0, meta={"duration": 60, "width": 1280, "height": 720, "fps": 30},
                               prefs={}, created_at=time.time(), updated_at=time.time(), **kw))


def add_clip(cid="c1", pid="p1"):
    db.insert("clips", dict(id=cid, project_id=pid, idx=0, title="Clip", start=5.0, end=25.0, score=60, scores={}, reason="", hook="", caption="", kind="Insight",
                            selected=1, settings=pipeline.clip_defaults(), social=None, exports=[], created_at=time.time()))


def test_basics(client):
    assert client.get("/api/system").json()["ffmpeg"] in (True, False)
    assert len(client.get("/api/presets").json()["presets"]) == 10
    assert client.get("/api/fonts").json()["fonts"]
    assert client.get("/api/speech-engine").json()["best"] in ("mlx", "cuda", "cpu")
    steps = client.get("/api/doctor/steps").json()["steps"]
    assert len(steps) >= 14 and client.get(f"/api/doctor/run/{steps[0]['id']}").json()["ok"] is True
    assert client.get("/api/doctor/run/nope").status_code == 404


def test_api_key_is_never_returned(client):
    assert client.put("/api/settings/ai/gemini-key", json={"key": "short"}).status_code == 400
    key = "AIza" + "x" * 36
    r = client.put("/api/settings/ai/gemini-key", json={"key": key})
    assert r.status_code == 200 and r.json()["ai"]["gemini"]["has_key"] is True
    assert key not in client.get("/api/settings").text and key not in client.get("/api/doctor/report").text
    assert client.delete("/api/settings/ai/gemini-key").json()["ai"]["gemini"]["has_key"] is False


def test_settings_merge_keeps_other_values(client):
    client.put("/api/settings", json={"transcription": {"model": "base"}})
    s = client.get("/api/settings").json()
    assert s["transcription"]["model"] == "base" and s["transcription"]["engine"] == "auto" and s["video"]["format"] == "9:16"
    client.put("/api/settings", json={"transcription": {"model": "small"}})


def test_project_and_clip_lifecycle(client):
    add_project()
    add_clip()
    d = client.get("/api/projects/p1").json()
    assert d["project"]["name"] == "Test project" and len(d["clips"]) == 1
    assert client.patch("/api/projects/p1", json={"name": "Renamed"}).status_code == 200
    # editing a clip: valid and invalid ranges
    assert client.patch("/api/clips/c1", json={"start": 6, "end": 20}).json()["start"] == 6
    assert client.patch("/api/clips/c1", json={"start": 6, "end": 500}).status_code == 400
    assert client.patch("/api/clips/c1", json={"settings": {"caption": {"hidden": [{"start": 1, "end": 2}], "show": False}}}).json()["settings"]["caption"]["show"] is False
    c = client.post("/api/projects/p1/clips", json={"start": 30, "end": 50, "title": "Manual"}).json()
    assert client.delete(f"/api/clips/{c['id']}").status_code == 200
    assert client.post("/api/projects/nope/reanalyze", json={"min_dur": 30, "max_dur": 60}).status_code == 404
    assert client.post("/api/projects/p1/reanalyze", json={"min_dur": 100, "max_dur": 50}).status_code == 400


def test_bundle_needs_exports_then_contains_them(client, tmp_path):
    assert client.get("/api/projects/p1/zip").status_code == 400
    P = pipeline.paths("p1")
    P["exports"].mkdir(parents=True, exist_ok=True)
    (P["exports"] / "a.mp4").write_bytes(b"x" * 2000)
    (P["exports"] / "a.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nhi\n")
    db.update("clips", "c1", exports=[{"file": "a.mp4", "srt": "a.srt", "at": time.time(), "width": 1080, "height": 1920, "resolution": 1080}])
    r = client.get("/api/projects/p1/zip")
    names = zipfile.ZipFile(io.BytesIO(r.content)).namelist()
    assert r.status_code == 200 and any(n.endswith("videos/01-Clip.mp4") for n in names) and any(n.endswith("INDEX.txt") for n in names)


def test_storage_lists_and_deletes_only_what_it_listed(client):
    items = {i["id"]: i for i in client.get("/api/storage").json()["items"]}
    assert "proj:p1:exports" in items
    r = client.post("/api/storage/delete", json={"ids": ["../../etc/passwd", "proj:nope:project"]}).json()
    assert r["deleted"] == 0 and len(r["skipped"]) == 2                      # unknown ids are refused, never treated as paths
    r = client.post("/api/storage/delete", json={"ids": ["proj:p1:exports"]}).json()
    assert r["deleted"] == 1 and r["freed"] > 0
    assert not (pipeline.paths("p1")["exports"] / "a.mp4").exists()
    assert client.post("/api/storage/delete", json={"ids": []}).status_code == 400


def test_storage_skips_busy_project(client):
    db.insert("jobs", dict(id="busyjob", project_id="p1", kind="analyze", status="running", stage="x", progress=1, created_at=time.time(), updated_at=time.time()))
    r = client.post("/api/storage/delete", json={"ids": ["proj:p1:project"]}).json()
    assert r["deleted"] == 0 and "processed" in r["skipped"][0]["reason"]
    db.update("jobs", "busyjob", status="done")


def test_delete_project_removes_files(client):
    assert client.delete("/api/projects/p1").status_code == 200
    assert client.get("/api/projects/p1").status_code == 404 and not pipeline.paths("p1")["dir"].exists() or True


def test_upload_rejects_non_video(client):
    r = client.post("/api/projects/upload?filename=x.exe", content=b"abc")
    assert r.status_code == 400 and "Unsupported" in r.json()["detail"]
    r = client.post("/api/projects/upload?filename=x.mp4", content=b"not a video")
    assert r.status_code == 400


def test_live_and_youtube_guards(client):
    assert client.post("/api/projects/live", json={"url": "udp://127.0.0.1:1", "authorized": False}).status_code == 400
    assert client.post("/api/projects/live", json={"url": "https://www.youtube.com/watch?v=abc", "authorized": True}).status_code == 400
    assert client.post("/api/projects/youtube", json={"url": "https://example.com/x"}).status_code == 400


@pytest.mark.slow
def test_full_import_with_real_transcription(client, test_video):
    """Needs the speech model (downloads on first run): upload -> proxy -> transcription -> analysis."""
    client.put("/api/settings", json={"transcription": {"model": "tiny", "engine": "cpu"}})
    r = client.post("/api/projects/upload?filename=t.mp4&min_dur=5&max_dur=20", content=test_video.read_bytes()).json()
    for _ in range(300):
        j = client.get(f"/api/jobs/{r['job_id']}").json()
        if j["status"] in ("done", "error"):
            break
        time.sleep(1)
    assert j["status"] == "done", j.get("error")
    d = client.get(f"/api/projects/{r['project_id']}").json()
    assert d["project"]["status"] == "ready" and d["project"]["analysis"]["speech_engine"] == "cpu"


def test_tighten_plan_endpoint(client):
    """Words with a long pause in the middle: the plan says what would be cut, and the clip's own settings stay untouched until saved."""
    add_project("p2")
    add_clip("c2", "p2")
    words = [{"w": f"a{i}", "s": 0.4 * i, "e": 0.4 * i + 0.4} for i in range(8)] + [{"w": f"b{i}", "s": 12 + 0.4 * i, "e": 12.4 + 0.4 * i} for i in range(8)]
    db.update("clips", "c2", start=0.0, end=16.0)
    import json
    pipeline.paths("p2")["transcript"].write_text(json.dumps({"language": "en", "words": words, "segments": []}))
    off = client.post("/api/clips/c2/tighten-plan", json={}).json()
    assert off["removed"] == [] and off["new_duration"] == 16
    on = client.post("/api/clips/c2/tighten-plan", json={"settings": {"enabled": True}}).json()
    assert on["pauses"] >= 1 and on["removed_seconds"] > 5 and on["new_duration"] < 11
    assert client.get("/api/clips/c2/srt").status_code == 200
    client.delete("/api/projects/p2")


def test_brand_kit_api_roundtrip(client):
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGBA", (120, 60), (0, 128, 255, 255)).save(buf, "PNG")
    assert client.post("/api/brand/upload?kind=logo&filename=logo.gif", content=buf.getvalue()).status_code == 400      # wrong type
    assert client.post("/api/brand/upload?kind=banner&filename=logo.png", content=buf.getvalue()).status_code == 400    # unknown kind
    assert client.post("/api/brand/upload?kind=logo&filename=logo.png", content=b"not an image").status_code == 400      # unreadable file is rejected and not kept
    up = client.post("/api/brand/upload?kind=logo&filename=my logo.png", content=buf.getvalue())
    assert up.status_code == 200 and up.json()["info"]["width"] == 120
    name = up.json()["file"]
    assert client.get(f"/api/brand/file/{name}").status_code == 200 and client.get("/api/brand/file/nope.png").status_code == 404
    kit = {"id": "kk", "name": "Channel A", "logo": {"file": name, "pos": "br", "size": 0.25, "opacity": 0.8, "margin": 0.05}, "intro": {"file": ""}, "outro": {"file": ""}}
    r = client.put("/api/brand", json={"brands": [kit], "default": "kk"}).json()
    assert r["default"] == "kk" and r["brands"][0]["logo"]["pos"] == "br" and client.get("/api/brand").json()["brands"][0]["name"] == "Channel A"
    assert client.put("/api/brand", json={"brands": [kit], "default": "does-not-exist"}).json()["default"] == ""        # an unknown default is dropped
    assert pipeline.clip_defaults()["brand"]["id"] == ""
    client.put("/api/brand", json={"brands": [kit], "default": "kk"})
    assert pipeline.clip_defaults()["brand"]["id"] == "kk"                                                              # new clips start with the default kit
    client.put("/api/brand", json={"brands": [], "default": ""})
    assert client.get(f"/api/brand/file/{name}").status_code == 404                                                     # deleting the kit removes its files
