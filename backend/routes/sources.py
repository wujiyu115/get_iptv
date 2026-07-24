from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services import github_service
from services import source_service as svc

router = APIRouter(prefix="/api")


class SourceIn(BaseModel):
    name: str | None = None
    url: str | None = None
    type: str | None = None
    enabled: int | None = None
    use_proxy: int | None = None
    sort: int | None = None
    note: str | None = None


@router.get("/sources")
def list_sources():
    return svc.list_sources()


@router.get("/sources/{sid}/github-updated")
def source_github_updated(sid: int):
    # One GitHub API call for this source only (null for non-raw.githubusercontent URLs).
    src = next((s for s in svc.list_sources() if s["id"] == sid), None)
    if src is None:
        raise HTTPException(status_code=404, detail="source not found")
    return {"id": sid, "updated": github_service.last_updated(src["url"])}


@router.post("/sources")
def create_source(body: SourceIn):
    return {"id": svc.create_source(body.model_dump(exclude_none=True))}


@router.put("/sources/{sid}")
def update_source(sid: int, body: SourceIn):
    svc.update_source(sid, body.model_dump(exclude_none=True))
    return {"ok": True}


@router.delete("/sources/{sid}")
def delete_source(sid: int):
    svc.delete_source(sid)
    return {"ok": True}
