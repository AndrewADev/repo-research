"""
GitHub API Tool Methods for AI Agents

This module provides a collection of functions for interacting with GitHub's API,
specifically designed to be used as tools by an AI agent. Each function is self-contained
and handles its own error checking and rate limiting.

Requirements:
    - PyGithub
    - python-dotenv
"""

from github import Github, Auth, GithubException, RateLimitExceededException
from typing import List, Dict, Optional
from datetime import datetime
import time
import os
from dotenv import load_dotenv

class GitHubTools:
    def __init__(self, token: Optional[str] = None):
        """
        Initialize GitHub tools with authentication.
        
        Args:
            token: GitHub personal access token. If None, will try to load from environment.
        """
        # Load environment variables if token not provided
        if token is None:
            load_dotenv()
            token = os.getenv('GITHUB_TOKEN')
            
        if not token:
            raise ValueError("GitHub token not provided and not found in environment")
            
        self.auth = Auth.Token(token)
        self.github = Github(auth=self.auth)
        
    def _handle_rate_limit(self) -> None:
        """Check rate limit and sleep if necessary."""
        rate_limit = self.github.get_rate_limit()
        if rate_limit.core.remaining < 10:
            reset_time = rate_limit.core.reset.timestamp() - time.time()
            if reset_time > 0:
                time.sleep(reset_time)

    def get_starred_repositories(self, username: Optional[str] = None, 
                               sort_by: str = "stars") -> List[Dict]:
        """
        Retrieve and sort starred repositories for a user.
        
        Args:
            username: GitHub username. If None, uses authenticated user.
            sort_by: How to sort results. Options: "stars", "recent", "issues"
        
        Returns:
            List of dictionaries containing repository information
        """
        try:
            self._handle_rate_limit()
            
            if username:
                user = self.github.get_user(username)
            else:
                user = self.github.get_user()
                
            starred_repos = []
            page = 0
            
            while True:
                repos_page = user.get_starred().get_page(page)
                if not repos_page:
                    break
                    
                for repo in repos_page:
                    repo_data = {
                        "name": repo.full_name,
                        "description": repo.description,
                        "stars": repo.stargazers_count,
                        "updated_at": repo.updated_at,
                        "open_issues": repo.open_issues_count,
                        "language": repo.language,
                        "url": repo.html_url
                    }
                    starred_repos.append(repo_data)
                
                page += 1
                time.sleep(0.5)  # Be nice to the API
                
            # Sort the results
            if sort_by == "stars":
                starred_repos.sort(key=lambda x: x["stars"], reverse=True)
            elif sort_by == "recent":
                starred_repos.sort(key=lambda x: x["updated_at"], reverse=True)
            elif sort_by == "issues":
                starred_repos.sort(key=lambda x: x["open_issues"], reverse=True)
                
            return starred_repos
            
        except RateLimitExceededException:
            raise Exception("GitHub API rate limit exceeded. Please try again later.")
        except GithubException as e:
            raise Exception(f"GitHub API error: {str(e)}")

    def analyze_repository_activity(self, repo_full_name: str) -> Dict:
        """
        Analyze recent activity in a repository.
        
        Args:
            repo_full_name: Full repository name (e.g., "username/repo")
            
        Returns:
            Dictionary containing activity metrics
        """
        try:
            self._handle_rate_limit()
            
            repo = self.github.get_repo(repo_full_name)
            
            # Get recent commits (last 30 days)
            recent_commits = 0
            thirty_days_ago = datetime.now().timestamp() - (30 * 24 * 60 * 60)
            
            for commit in repo.get_commits():
                if commit.commit.author.date.timestamp() < thirty_days_ago:
                    break
                recent_commits += 1
                
            # Get open issues and PRs
            open_issues = repo.get_issues(state='open').totalCount
            open_prs = repo.get_pulls(state='open').totalCount
            
            activity_data = {
                "recent_commits": recent_commits,
                "open_issues": open_issues,
                "open_pull_requests": open_prs,
                "stargazers": repo.stargazers_count,
                "forks": repo.forks_count,
                "last_push": repo.pushed_at,
                "created_at": repo.created_at,
                "primary_language": repo.language
            }
            
            return activity_data
            
        except RateLimitExceededException:
            raise Exception("GitHub API rate limit exceeded. Please try again later.")
        except GithubException as e:
            raise Exception(f"GitHub API error: {str(e)}")

    def search_repositories(self, query: str, 
                          sort: Optional[str] = "stars",
                          limit: int = 10) -> List[Dict]:
        """
        Search for repositories matching criteria.
        
        Args:
            query: Search query string
            sort: How to sort results ("stars", "forks", "updated")
            limit: Maximum number of results to return
            
        Returns:
            List of matching repositories
        """
        try:
            self._handle_rate_limit()
            
            results = []
            repositories = self.github.search_repositories(query=query, sort=sort)
            
            for repo in repositories[:limit]:
                repo_data = {
                    "name": repo.full_name,
                    "description": repo.description,
                    "stars": repo.stargazers_count,
                    "forks": repo.forks_count,
                    "language": repo.language,
                    "url": repo.html_url,
                    "updated_at": repo.updated_at
                }
                results.append(repo_data)
                
            return results
            
        except RateLimitExceededException:
            raise Exception("GitHub API rate limit exceeded. Please try again later.")
        except GithubException as e:
            raise Exception(f"GitHub API error: {str(e)}")

    def get_user_profile(self, username: Optional[str] = None) -> Dict:
        """
        Get detailed information about a GitHub user.
        
        Args:
            username: GitHub username. If None, uses authenticated user.
            
        Returns:
            Dictionary containing user information
        """
        try:
            self._handle_rate_limit()
            
            if username:
                user = self.github.get_user(username)
            else:
                user = self.github.get_user()
                
            profile_data = {
                "login": user.login,
                "name": user.name,
                "bio": user.bio,
                "location": user.location,
                "public_repos": user.public_repos,
                "followers": user.followers,
                "following": user.following,
                "created_at": user.created_at,
                "updated_at": user.updated_at,
                "email": user.email
            }
            
            return profile_data
            
        except RateLimitExceededException:
            raise Exception("GitHub API rate limit exceeded. Please try again later.")
        except GithubException as e:
            raise Exception(f"GitHub API error: {str(e)}")

    def close(self) -> None:
        """Close the GitHub connection."""
        self.github.close()
