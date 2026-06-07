import typer


def ui(
    share: bool = typer.Option(False, "--share", help="Create a public share link"),
    server_name: str = typer.Option(
        "127.0.0.1", "--host", help="Server hostname/IP address"
    ),
    server_port: int = typer.Option(7860, "--port", help="Server port number"),
):
    """Launch the Gradio web UI"""
    from ui import launch_ui

    print(f"\n🚀 Launching Gradio UI on http://{server_name}:{server_port}")
    launch_ui(share=share, server_name=server_name, server_port=server_port)


def register(app: typer.Typer) -> None:
    app.command()(ui)
