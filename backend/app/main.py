import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import config, db, jobs

config.setup_logging()
log = logging.getLogger("clipforge")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init()
    jobs.recover_interrupted()
    jobs.clean_temp_downloads()
    log.info("ClipForge backend ready. ffmpeg=%s", config.FFMPEG)
    yield


app = FastAPI(title="ClipForge AI", lifespan=lifespan)
# Local-only app: only the local frontend may call it from a browser.
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"], allow_methods=["*"], allow_headers=["*"])

from .routers import api  # noqa: E402

app.include_router(api.router, prefix="/api")
app.mount("/media", StaticFiles(directory=config.PROJECTS_DIR), name="media")
app.mount("/fonts", StaticFiles(directory=config.FONTS_DIR), name="fonts")
