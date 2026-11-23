import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .actor import router as actor_router
from .course_routes import router as course_router
from .certificate_routes import router as certificate_router
from .errors import install_error_handlers


def create_app(db_path: Path, frontend_dist: Path | None = None) -> FastAPI:
    app = FastAPI()
    app.state.db_path = Path(db_path)
    app.state.frontend_dist = frontend_dist
    install_error_handlers(app)
    app.include_router(actor_router)
    app.include_router(course_router)
    app.include_router(certificate_router)

    if frontend_dist is not None and (frontend_dist / "index.html").is_file():
        assets = frontend_dist / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/", include_in_schema=False)
        @app.get("/certificates", include_in_schema=False)
        @app.get("/courses", include_in_schema=False)
        def frontend_page() -> FileResponse:
            return FileResponse(frontend_dist / "index.html")

    @app.middleware("http")
    async def no_store_api(request: Request, call_next):
        response = await call_next(request)
        if request.method == "GET" and request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    return app


app = create_app(
    Path(os.getenv("TRAINING_DB_PATH", "data/training.sqlite3")),
    Path(os.getenv("TRAINING_FRONTEND_DIST", "frontend/dist")),
)
