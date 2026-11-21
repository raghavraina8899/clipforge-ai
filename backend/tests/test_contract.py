"""Every address the website calls must exist in the backend. Catches an endpoint being lost or renamed
(this is how a deleted "Convert captions to Hinglish" endpoint slipped through once)."""
import re
from pathlib import Path

import pytest

from app.main import app

FRONT = Path(__file__).resolve().parents[2] / "frontend"
CALL = re.compile(r"\b(?:api|upload)(?:<[^>()]*>)?\(\s*([`\"'])(/[^`\"']*)\1")
DIRECT = re.compile(r"\$\{API\}(/api/[^`\"']*)")


def frontend_paths() -> dict:
    found: dict = {}
    for ext in ("*.ts", "*.tsx"):
        for f in FRONT.rglob(ext):
            if any(x in f.parts for x in ("node_modules", "node_modules.nosync", ".next", ".next.nosync")):
                continue
            text = f.read_text(errors="ignore")
            for m in CALL.finditer(text):
                found.setdefault("/api" + m.group(2), f.name)
            for m in DIRECT.finditer(text):
                found.setdefault(m.group(1), f.name)
    out = {}
    for path, name in found.items():
        norm = re.sub(r"\$\{[^}]*\}", "x", path.split("?")[0])
        out[norm] = name
    return out


def route_regexes() -> list:
    # the app's own API description lists every route (app.routes hides included routers in newer FastAPI versions)
    return [re.compile("^" + re.sub(r"\{[^/}]+\}", "[^/]+", path) + "$") for path in app.openapi()["paths"]]


@pytest.mark.skipif(not FRONT.exists(), reason="frontend folder not present")
def test_every_frontend_call_has_a_backend_route():
    paths = frontend_paths()
    assert len(paths) > 40, "the scan found too few calls; the regex needs updating"
    assert "/api/projects/x/romanize" in paths and "/api/projects/x/retry" in paths     # known calls must be seen by the scan
    regs = route_regexes()
    missing = {p: f for p, f in paths.items() if not any(r.match(p) for r in regs)}
    assert not missing, f"the website calls addresses the backend does not have: {missing}"
