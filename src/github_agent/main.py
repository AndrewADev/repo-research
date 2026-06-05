import typer
from dotenv import load_dotenv

from github_agent import commands
from github_agent.commands.chat import chat
from github_agent.commands.runners import (
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
