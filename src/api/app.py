"""FastAPI application factory for the Repo Research API.

Exposes the existing LangGraph agent over the AG-UI protocol (`POST /agent`,
streamed as SSE) plus REST endpoints for conversation history, favorites, and
runtime config. The React SPA (pnpm + Vite + CopilotKit) is the primary client.
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import agent_endpoint, config, conversations, favorites

# Allow the Vite dev server by default; override with API_CORS_ORIGINS (comma list).
_DEFAULT_CORS_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


def _cors_origins() -> list[str]:
    raw = os.environ.get("API_CORS_ORIGINS")
    if not raw:
        return _DEFAULT_CORS_ORIGINS
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    app = FastAPI(title="Repo Research API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type", "Accept"],
    )

    app.include_router(agent_endpoint.router)
    app.include_router(conversations.router, prefix="/api")
    app.include_router(favorites.router, prefix="/api")
    app.include_router(config.router, prefix="/api")

    return app
