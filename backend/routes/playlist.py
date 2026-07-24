import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from config.config_loader import config

router = APIRouter()

_MEDIA = {"full.m3u": "audio/x-mpegurl", "compact.m3u": "audio/x-mpegurl",
          "iptv.txt": "text/plain; charset=utf-8"}


def _serve(name: str):
    out_dir = os.environ.get("OUTPUT_DIR") or config.get("output.dir", "./output")
    path = os.path.join(out_dir, name)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="not generated yet")
    return FileResponse(path, media_type=_MEDIA[name])


@router.get("/full.m3u")
def full(): return _serve("full.m3u")


@router.get("/compact.m3u")
def compact(): return _serve("compact.m3u")


@router.get("/iptv.txt")
def txt(): return _serve("iptv.txt")
