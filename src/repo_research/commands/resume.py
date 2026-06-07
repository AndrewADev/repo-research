import typer

from .runners import resume_conversation


def resume(
    thread_id: str = typer.Argument(
        None, help="Thread ID to resume (omit to use --last)"
    ),
    last: bool = typer.Option(
        False, "--last", help="Resume the most recent conversation"
    ),
    model_name: str = typer.Option(
        None, "--model-name", help="Override the model name for this command"
    ),
):
    """Resume an existing conversation interactively"""
    try:
        resume_conversation(thread_id=thread_id, last=last, model_name=model_name)
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from e
    except LookupError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from e


def register(app: typer.Typer) -> None:
    app.command()(resume)
