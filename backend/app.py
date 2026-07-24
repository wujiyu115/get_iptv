import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from db.database import init_db
from utils.logger import logger

current_dir = os.path.dirname(os.path.abspath(__file__))


def create_app() -> FastAPI:
    app = FastAPI(title="IPTV 聚合服务", version="1.0.0")
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_credentials=True,
        allow_methods=["*"], allow_headers=["*"])

    init_db()

    from routes.sources import router as sources_router
    from routes.aliases import router as aliases_router
    from routes.templates import router as templates_router
    from routes.tasks import router as tasks_router
    from routes.channels import router as channels_router
    from routes.reports import router as reports_router
    from routes.playlist import router as playlist_router
    for r in (sources_router, aliases_router, templates_router, tasks_router,
              channels_router, reports_router, playlist_router):
        app.include_router(r)

    try:
        from scheduler import scheduler
        scheduler.start()
    except Exception as e:  # noqa: BLE001
        logger.warning("scheduler not started: %s", e)

    static_folder = os.getenv("FRONTEND") or os.path.join(current_dir, "../frontend/dist")
    if os.path.exists(static_folder):
        static_assets = os.path.join(static_folder, "static")
        if os.path.exists(static_assets):
            app.mount("/static", StaticFiles(directory=static_assets), name="static")

        @app.get("/{full_path:path}")
        async def serve_spa(request: Request, full_path: str):
            if full_path.startswith("api/"):
                return JSONResponse({"message": "Not Found"}, status_code=404)
            if ".." in full_path or full_path.startswith("/") or "\\" in full_path:
                return JSONResponse({"message": "Access Denied"}, status_code=403)
            file_path = os.path.join(static_folder, full_path)
            real = os.path.realpath(file_path)
            root = os.path.realpath(static_folder)
            if real != root and not real.startswith(root + os.sep):
                return JSONResponse({"message": "Access Denied"}, status_code=403)
            if os.path.isfile(file_path):
                return FileResponse(file_path)
            index_path = os.path.join(static_folder, "index.html")
            if os.path.exists(index_path):
                return FileResponse(index_path, media_type="text/html")
            return JSONResponse({"message": "Frontend not found"}, status_code=404)

    logger.info("IPTV app created")
    return app


app = create_app()
