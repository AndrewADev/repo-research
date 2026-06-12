"""Favorites REST endpoints, backed by the server-side FavoriteStore."""

from fastapi import APIRouter, HTTPException, Response

from api.schemas import FavoritesOut, SavedRepositoryIn
from storage import FavoriteStore, SavedRepository

router = APIRouter()


@router.get("/favorites")
def list_favorites() -> FavoritesOut:
    """Return all saved repositories."""
    with FavoriteStore() as store:
        return FavoritesOut(saved_repos=store.list())


@router.post("/favorites")
def add_favorite(repo: SavedRepositoryIn) -> FavoritesOut:
    """Save a repository to favorites (idempotent on full_name)."""
    with FavoriteStore() as store:
        store.add(SavedRepository(**repo.model_dump()))
        return FavoritesOut(saved_repos=store.list())


@router.get("/favorites/export")
def export_favorites() -> Response:
    """Download all favorites as a CSV file."""
    with FavoriteStore() as store:
        csv_content = store.export_csv()
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=favorites.csv"},
    )


@router.delete("/favorites/{full_name:path}")
def remove_favorite(full_name: str) -> FavoritesOut:
    """Remove a repository from favorites by full name (``owner/repo``)."""
    with FavoriteStore() as store:
        if not store.remove(full_name):
            raise HTTPException(status_code=404, detail="Favorite not found")
        return FavoritesOut(saved_repos=store.list())
