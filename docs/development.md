# Development

## Setup

Install all dependencies including dev tools with:
```shell
uv sync --dev
```

## Pre-commit hooks

You will also need to make sure you can run the pre-commit hooks, which are generally run with `prek`:

```shell
uv tool install prek
```

Check the output to see if any additional steps are needed (e.g. profile or $PATH updates) then restart you shell, if necessary.

Now you should be able to run the pre-commit checks:

```shell
prek run
```

For best results, you should install them to be run automatically:
```shell
prek install
```

## Linting & formatting
Linting and formatting available via:
- `uv run ruff check` - Run linting checks
- `uv run ruff format` - Format code
- `uv run ruff check --fix` - Auto-fix linting issues

## CLI documentation

The CLI reference section in the [README](../README.md) (and [docs/cli.md](cli.md)) is generated from the live Typer app. After changing any command, regenerate with:

```shell
uv run python scripts/update_cli_docs.py
```

A pre-commit hook (`cli-docs`) runs the same command automatically and is checked in CI — pass `--check` to verify without writing:

```shell
uv run python scripts/update_cli_docs.py --check
```


## Observability and traces (LangSmith)

Being a LangGraph project, it is easy to set up observability with LangSmith.

After signing into your account (optionally creating a new project), simply copy over the following values to your `.env` file:
```dotenv
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://api.smith.langchain.com # Or your endpoint
LANGSMITH_API_KEY=<your API key>
LANGSMITH_PROJECT=<your proj name>
```

Be sure not to include sensitive values in files you commit to source!
