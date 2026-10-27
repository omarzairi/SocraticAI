from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import Settings
from app.database import init_db
from app.errors import NotFoundError
from app.routers import learners

# The Next.js dev server, reachable under both names.
FRONTEND_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the app. Tests pass their own settings; the server uses .env and defaults."""
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db(settings.database_path)
        yield

    app = FastAPI(title="SocraticAI", lifespan=lifespan)
    app.state.settings = settings

    # allow_methods defaults to GET only, which would block POST, PATCH and DELETE preflights.
    app.add_middleware(
        CORSMiddleware, allow_origins=FRONTEND_ORIGINS, allow_methods=["*"], allow_headers=["*"]
    )

    @app.exception_handler(NotFoundError)
    async def handle_not_found(request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.get("/api/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(learners.router)
    return app


app = create_app()
