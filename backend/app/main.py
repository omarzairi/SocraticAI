from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings

# The Next.js dev server, reachable under both names.
FRONTEND_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the app. Tests pass their own settings; the server uses .env and defaults."""
    settings = settings or Settings()

    app = FastAPI(title="SocraticAI")
    app.state.settings = settings

    # allow_methods defaults to GET only, which would block POST, PATCH and DELETE preflights.
    app.add_middleware(
        CORSMiddleware, allow_origins=FRONTEND_ORIGINS, allow_methods=["*"], allow_headers=["*"]
    )

    @app.get("/api/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
