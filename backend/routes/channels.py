from fastapi import APIRouter, Query

from services import channel_service as svc

router = APIRouter(prefix="/api")


@router.get("/channels")
def list_channels(run: str = Query("latest")):
    return svc.list_channels(run)
