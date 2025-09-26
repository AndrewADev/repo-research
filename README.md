
# GitHub Tools

## Usage

### Example usage

```python
if __name__ == "__main__":
    # Initialize the tools
    github_tools = GitHubTools()
    
    try:
        # Get and print starred repositories
        starred = github_tools.get_starred_repositories(sort_by="stars")
        print(f"Found {len(starred)} starred repositories")
        
        # Search for repositories
        python_repos = github_tools.search_repositories("language:python stars:>1000", 
                                                      sort="stars", 
                                                      limit=5)
        print(f"Found {len(python_repos)} matching repositories")
        
    finally:
        # Always close the connection
        github_tools.close()
```


## Development

### Setup

Install all dependencies including dev tools with:
```
uv sync --dev
```


### Linting & formatting
Linting and formatting available via:
- `uv run ruff check` - Run linting checks
- `uv run ruff format` - Format code
- `uv run ruff check --fix` - Auto-fix linting issues