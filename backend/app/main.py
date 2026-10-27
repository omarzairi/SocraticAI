import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import Settings
from app.database import init_db
from app.errors import ConflictError, NotFoundError
from app.llm import LLMError, OpenAICompatibleClient
from app.routers import learners, sessions

logger = logging.getLogger(__name__)

# The Next.js dev server, reachable under both names.
FRONTEND_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the app. Tests pass their own settings; the server reads backend/.env at startup."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s - %(message)s")
        # Read settings when the server starts, not when this module is imported, so importing
        # the module (as the tests do) never touches the developer's backend/.env.
        app.state.settings = settings or Settings()
        init_db(app.state.settings.database_path)
        app.state.llm_client = OpenAICompatibleClient(app.state.settings)
        logger.info("Using database %s", app.state.settings.database_path)
        if not app.state.settings.llm_api_key.get_secret_value():
            logger.error("LLM_API_KEY is not set: the tutor can't answer until you add it to .env")
        yield

    app = FastAPI(title="SocraticAI", lifespan=lifespan)

    # allow_methods defaults to GET only, which would block POST, PATCH and DELETE preflights.
    app.add_middleware(
        CORSMiddleware, allow_origins=FRONTEND_ORIGINS, allow_methods=["*"], allow_headers=["*"]
    )

    @app.exception_handler(NotFoundError)
    async def handle_not_found(request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ConflictError)
    async def handle_conflict(request: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(LLMError)
    async def handle_llm_error(request: Request, exc: LLMError) -> JSONResponse:
        # 502 Bad Gateway: our server is fine, but the upstream AI provider failed us.
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    @app.get("/api/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(learners.router)
    app.include_router(sessions.router)
    return app


app = create_app()
