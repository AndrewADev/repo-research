
## GitHub Tools

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