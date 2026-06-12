"""Repository favorites models.

These now live in :mod:`storage.favorites` so the React SPA (via the API) and the
legacy Gradio UI share a single definition. Re-exported here for backwards
compatibility with existing Gradio handler imports.
"""

from storage.favorites import FavoritesState, SavedRepository

__all__ = ["FavoritesState", "SavedRepository"]
