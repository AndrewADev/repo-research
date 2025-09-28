
# GitHub Tools

## Usage

### Example usage

```shell
uv run agent.py analyze
```

Available commands:
```shell
uv run agent.py --help
```


## Development

### Setup

Install all dependencies including dev tools with:
```shell
uv sync --dev
```

### Pre-commit hooks

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

### Linting & formatting
Linting and formatting available via:
- `uv run ruff check` - Run linting checks
- `uv run ruff format` - Format code
- `uv run ruff check --fix` - Auto-fix linting issues
