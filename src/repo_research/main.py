import typer
from dotenv import load_dotenv

from repo_research import commands
from repo_research.commands.chat import chat
from repo_research.commands.runners import (
    resume_conversation,
    run_interactive_session,
    run_prompt,
    run_templated_prompt,
)

load_dotenv()

app = typer.Typer(rich_markup_mode="rich")

for _module in (
    commands.diagnostics,
    commands.pulse,
    commands.topics,
    commands.hotspots,
    commands.history,
    commands.show,
    commands.chat,
    commands.resume,
    commands.ui,
    commands.serve,
):
    _module.register(app)


__all__ = [
    "app",
    "chat",
    "resume_conversation",
    "run_interactive_session",
    "run_prompt",
    "run_templated_prompt",
]


if __name__ == "__main__":
    app()
