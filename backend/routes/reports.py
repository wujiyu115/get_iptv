from fastapi import APIRouter

from services import report_service as svc

router = APIRouter(prefix="/api")


@router.get("/reports")
def reports():
    return svc.report()
