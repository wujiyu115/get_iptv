from fastapi import APIRouter
from pydantic import BaseModel

from services import settings_service as svc

router = APIRouter(prefix="/api")

PROXY_KEY = "fetch.http_proxy"


class ProxyIn(BaseModel):
    http_proxy: str = ""


@router.get("/settings/proxy")
def get_proxy():
    return {"http_proxy": svc.get(PROXY_KEY, "")}


@router.put("/settings/proxy")
def set_proxy(body: ProxyIn):
    svc.set(PROXY_KEY, body.http_proxy.strip())
    return {"ok": True, "http_proxy": body.http_proxy.strip()}
