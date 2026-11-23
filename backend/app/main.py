import os
from pathlib import Path

from fastapi import FastAPI, Request

from .actor import router as actor_router
from .course_routes import router as course_router
from .errors import install_error_handlers


def create_app(db_path: Path, frontend_dist: Path | None = None) -> FastAPI:
    app = FastAPI()
    app.state.db_path = Path(db_path)
    app.state.frontend_dist = frontend_dist
    install_error_handlers(app)
    app.include_router(actor_router)
    app.include_router(course_router)

    @app.middleware("http")
    async def no_store_api(request: Request, call_next):
        response = await call_next(request)
        if request.method == "GET" and request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    return app


app = create_app(Path(os.getenv("TRAINING_DB_PATH", "data/training.sqlite3")))
