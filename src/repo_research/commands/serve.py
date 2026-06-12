import json
from pathlib import Path

import typer


def serve(
    host: str = typer.Option("127.0.0.1", "--host", help="Server hostname/IP address"),
    port: int = typer.Option(8000, "--port", help="Server port number"),
    reload: bool = typer.Option(
        False, "--reload", help="Auto-reload on code changes (development)"
    ),
) -> None:
    """Launch the HTTP API server (FastAPI) for the React SPA."""
    import uvicorn

    print(f"\n🚀 Launching Repo Research API on http://{host}:{port}")
    if reload:
        # Reload requires an import string + app factory, not an app instance.
        uvicorn.run(
            "api.app:create_app", factory=True, host=host, port=port, reload=True
        )
    else:
        from api.app import create_app

        uvicorn.run(create_app(), host=host, port=port)


def export_openapi(
    output: str = typer.Option(
        "frontend/openapi.json", "--output", "-o", help="Where to write the schema"
    ),
) -> None:
    """Write the API's OpenAPI schema to disk (for offline TS type generation)."""
    from api.app import create_app

    schema = create_app().openapi()
    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(schema, indent=2))
    print(f"✅ Wrote OpenAPI schema to {out_path}")


def register(app: typer.Typer) -> None:
    app.command()(serve)
    app.command(name="export-openapi")(export_openapi)
