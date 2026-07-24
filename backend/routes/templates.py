from fastapi import APIRouter
from pydantic import BaseModel

from services import source_service as svc

router = APIRouter(prefix="/api")


class TemplateIn(BaseModel):
    canonical: str | None = None
    group_title: str | None = None
    logo: str | None = None
    sort: int | None = None
    enabled: int | None = None


@router.get("/templates")
def list_templates():
    return svc.list_templates()


@router.post("/templates")
def create_template(body: TemplateIn):
    return {"id": svc.create_template(body.model_dump(exclude_none=True))}


@router.put("/templates/{tid}")
def update_template(tid: int, body: TemplateIn):
    svc.update_template(tid, body.model_dump(exclude_none=True))
    return {"ok": True}


@router.delete("/templates/{tid}")
def delete_template(tid: int):
    svc.delete_template(tid)
    return {"ok": True}
