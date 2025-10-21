
# GitHub Tools

## Usage

### Example usage (uv-based, local)

```shell
uv sync
```

```shell
uv run github-agent analyze
```

### Commands

Available commands:
```shell
uv run github-agent --help
```

#### Activity analysis (starred repo pulse)

The `pulse` command will run some basic analysis on how active repos are, such as the number of open issues, recent commit count etc. For now, it runs against the users starred repositories (by default looking at the most recenly updated ones).

See `pulse --help` for more details.


#### Topic-based search

Search for projects/repositories based on "topics", with the ability to specify various filter criteria (such as recency, license, language, etc.)

Examples:
```shell
uv run github-agent topics "ai,machine-learning"

# With language and recency filter
uv run github-agent topics "llm" --language python --pushed-within-days 30

# Comprehensive filtering
uv run github-agent topics "web-framework" --language rust --license mit --min-stars 1000 --fork false
--archived false
```

#### Hotspot analysis

Specifying the `hotspots` command will kick off a workflow that looks at things such as:
* Number and type of changes over a period
* Number of authors of changes
* Concentration of these per file

Additionally, it will calculate some simplistic "churn" metrics, before performing an analysis, which can be exported to a markdown format by providing the `--export-md` flag.

Note that it is possible to limit analysis to a particular path. See the `hotspots --help` command for these and other details.


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


### Observability and traces (LangSmith)

Being a LangGraph project, it is easy to set up observability with LangSmith.

After signing into your account (optionally creating a new project), simply copy over the following values to your `.env` file:
```dotenv
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://api.smith.langchain.com # Or your endpoint
LANGSMITH_API_KEY=<your API key>
LANGSMITH_PROJECT=<your proj name>
```

Be sure not to include sensitive values in files you commit to source!
