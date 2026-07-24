from fastapi import APIRouter
from pydantic import BaseModel

from services import source_service as svc

router = APIRouter(prefix="/api")


class AliasIn(BaseModel):
    canonical: str | None = None
    pattern: str | None = None
    is_regex: int | None = None
    enabled: int | None = None


@router.get("/aliases")
def list_aliases():
    return svc.list_aliases()


@router.post("/aliases")
def create_alias(body: AliasIn):
    return {"id": svc.create_alias(body.model_dump(exclude_none=True))}


@router.put("/aliases/{aid}")
def update_alias(aid: int, body: AliasIn):
    svc.update_alias(aid, body.model_dump(exclude_none=True))
    return {"ok": True}


@router.delete("/aliases/{aid}")
def delete_alias(aid: int):
    svc.delete_alias(aid)
    return {"ok": True}
