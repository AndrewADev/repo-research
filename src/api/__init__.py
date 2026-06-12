"""HTTP API package: FastAPI app serving the agent (AG-UI SSE) and REST routes."""

from api.app import create_app

__all__ = ["create_app"]
