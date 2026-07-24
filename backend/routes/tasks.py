import asyncio

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from services import run_service

router = APIRouter(prefix="/api")


class ScheduleIn(BaseModel):
    update_mode: str | None = None
    update_interval: int | None = None
    update_times: list[str] | None = None
    update_startup: bool | None = None
    time_zone: str | None = None


@router.post("/tasks/run")
def trigger():
    try:
        run_service.start_run_async()
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"ok": True}


@router.get("/tasks/status")
def status():
    return run_service.snapshot()


@router.get("/tasks/logs")
async def logs():
    q = run_service.subscribe()
    snap = run_service.snapshot()

    async def gen():
        try:
            for line in snap["logs"]:
                yield f"data: {line}\n\n"
            while True:
                try:
                    line = q.get_nowait()
                    yield f"data: {line}\n\n"
                except Exception:  # noqa: BLE001
                    await asyncio.sleep(0.5)
                    yield ": keepalive\n\n"
        finally:
            run_service.unsubscribe(q)

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.get("/tasks/schedule")
def get_schedule():
    from scheduler import scheduler
    return scheduler.get_schedule()


@router.put("/tasks/schedule")
def set_schedule(body: ScheduleIn):
    from scheduler import scheduler
    scheduler.set_schedule(body.model_dump(exclude_none=True))
    return {"ok": True}
