"""
Redis-Cached GitHub API Tool Methods for AI Agents

This module extends the GitHubTools class with Redis caching capabilities.
Falls back gracefully to direct API calls when Redis is not available.

Requirements:
    - PyGithub
    - redis
    - python-dotenv
    - tenacity (for retry logic)
"""

from github import Github, Auth, GithubException, RateLimitExceededException
from typing import List, Dict, Optional, Any, Callable
from datetime import datetime, timedelta
import time
import os
import json
import hashlib
import redis
from functools import wraps
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

class CachedGitHubTools:
    def __init__(self, token: Optional[str] = None, redis_url: Optional[str] = None):
        """
        Initialize GitHub tools with optional Redis caching.
        
        Args:
            token: GitHub personal access token
            redis_url: Redis connection URL (e.g., 'redis://localhost:6379/0')
        """
        # Load environment variables if needed
        load_dotenv()
        
        # Initialize GitHub client
        if token is None:
            token = os.getenv('GITHUB_TOKEN')
        if not token:
            raise ValueError("GitHub token not provided and not found in environment")
            
        self.auth = Auth.Token(token)
        self.github = Github(auth=self.auth)
        
        # Initialize Redis client (optional)
        self.redis_client = None
        self.redis_available = False
        
        if redis_url is None:
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
            
        if redis_url:
            try:
                self.redis_client = redis.from_url(redis_url, decode_responses=True)
                # Test connection
                self.redis_client.ping()
                self.redis_available = True
                print("✅ Redis cache enabled")
            except (redis.ConnectionError, redis.TimeoutError) as e:
                print(f"⚠️  Redis not available, falling back to direct API calls: {e}")
                self.redis_client = None
                self.redis_available = False

    def _generate_cache_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate a consistent cache key from method arguments."""
        # Create a string representation of args and kwargs
        key_data = f"{prefix}:" + ":".join(str(arg) for arg in args)
        if kwargs:
            sorted_kwargs = sorted(kwargs.items())
            key_data += ":" + ":".join(f"{k}={v}" for k, v in sorted_kwargs)
        
        # Hash long keys to keep them manageable
        if len(key_data) > 200:
            key_hash = hashlib.md5(key_data.encode()).hexdigest()
            return f"{prefix}:hash:{key_hash}"
        
        return key_data.replace(" ", "_").lower()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(redis.ConnectionError)
    )
    def _get_from_cache(self, key: str) -> Optional[Any]:
        """Get data from Redis cache with retry logic."""
        if not self.redis_available:
            return None
        
        try:
            cached_data = self.redis_client.get(key)
            if cached_data:
                return json.loads(cached_data)
        except (redis.ConnectionError, json.JSONDecodeError) as e:
            print(f"Cache read error for key {key}: {e}")
        
        return None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(redis.ConnectionError)
    )
    def _set_in_cache(self, key: str, data: Any, ttl_seconds: int) -> None:
        """Set data in Redis cache with retry logic."""
        if not self.redis_available:
            return
        
        try:
            serialized_data = json.dumps(data, default=str, ensure_ascii=False)
            self.redis_client.setex(key, ttl_seconds, serialized_data)
        except (redis.ConnectionError, TypeError) as e:
            print(f"Cache write error for key {key}: {e}")

    def cached_method(self, ttl_hours: int = 1):
        """
        Decorator to add caching to GitHub API methods.
        
        Args:
            ttl_hours: Time-to-live in hours for cached data
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Generate cache key
                method_name = func.__name__
                cache_key = self._generate_cache_key(method_name, *args[1:], **kwargs)
                
                # Try to get from cache first
                cached_result = self._get_from_cache(cache_key)
                if cached_result is not None:
                    print(f"🎯 Cache hit for {method_name}")
                    return cached_result
                
                # Cache miss - call the actual method
                print(f"🔍 Cache miss for {method_name}, querying GitHub API")
                result = func(*args, **kwargs)
                
                # Cache the result
                ttl_seconds = ttl_hours * 3600
                self._set_in_cache(cache_key, result, ttl_seconds)
                
                return result
            return wrapper
        return decorator

    def _handle_rate_limit(self) -> None:
        """Check rate limit and sleep if necessary."""
        rate_limit = self.github.get_rate_limit()
        if rate_limit.core.remaining < 10:
            reset_time = rate_limit.core.reset.timestamp() - time.time()
            if reset_time > 0:
                print(f"⏳ Rate limit reached, sleeping for {reset_time:.1f} seconds")
                time.sleep(reset_time)

    @cached_method(ttl_hours=24)  # User profiles change infrequently
    def get_user_profile(self, username: Optional[str] = None) -> Dict:
        """Get detailed information about a GitHub user."""
        try:
            self._handle_rate_limit()
            
            if username:
                user = self.github.get_user(username)
            else:
                user = self.github.get_user()
                
            return {
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
            
        except RateLimitExceededException:
            raise Exception("GitHub API rate limit exceeded. Please try again later.")
        except GithubException as e:
            raise Exception(f"GitHub API error: {str(e)}")

    @cached_method(ttl_hours=6)  # Repository metadata changes moderately
    def analyze_repository_activity(self, repo_full_name: str) -> Dict:
        """Analyze recent activity in a repository."""
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
            
            return {
                "recent_commits": recent_commits,
                "open_issues": open_issues,
                "open_pull_requests": open_prs,
                "stargazers": repo.stargazers_count,
                "forks": repo.forks_count,
                "last_push": repo.pushed_at,
                "created_at": repo.created_at,
                "primary_language": repo.language
            }
            
        except RateLimitExceededException:
            raise Exception("GitHub API rate limit exceeded. Please try again later.")
        except GithubException as e:
            raise Exception(f"GitHub API error: {str(e)}")

    @cached_method(ttl_hours=2)  # Starred repos change somewhat frequently
    def get_starred_repositories(self, username: Optional[str] = None, 
                               sort_by: str = "stars") -> List[Dict]:
        """Retrieve and sort starred repositories for a user."""
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

    @cached_method(ttl_hours=0.5)  # Search results change frequently
    def search_repositories(self, query: str, 
                          sort: Optional[str] = "stars",
                          limit: int = 10) -> List[Dict]:
        """Search for repositories matching criteria."""
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

    def invalidate_cache(self, pattern: str = None) -> None:
        """
        Invalidate cache entries matching a pattern.
        
        Args:
            pattern: Redis key pattern (e.g., 'get_user_profile:*')
        """
        if not self.redis_available:
            return
            
        if pattern is None:
            # Clear all cache
            for key in self.redis_client.scan_iter():
                self.redis_client.delete(key)
            print("🗑️  All cache cleared")
        else:
            # Clear specific pattern
            keys = list(self.redis_client.scan_iter(match=pattern))
            if keys:
                self.redis_client.delete(*keys)
                print(f"🗑️  Cleared {len(keys)} cache entries matching '{pattern}'")

    def get_cache_stats(self) -> Dict:
        """Get Redis cache statistics."""
        if not self.redis_available:
            return {"status": "disabled"}
            
        try:
            info = self.redis_client.info()
            return {
                "status": "enabled",
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "unknown"),
                "total_commands_processed": info.get("total_commands_processed", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "hit_rate": (
                    info.get("keyspace_hits", 0) / 
                    max(info.get("keyspace_hits", 0) + info.get("keyspace_misses", 0), 1)
                ) * 100
            }
        except redis.ConnectionError:
            return {"status": "connection_error"}

    def close(self) -> None:
        """Close GitHub and Redis connections."""
        self.github.close()
        if self.redis_client:
            self.redis_client.close()


# Example usage
if __name__ == "__main__":
    # Initialize with Redis caching
    github_tools = CachedGitHubTools()
    
    try:
        # This will cache the result for 24 hours
        profile = github_tools.get_user_profile("octocat")
        print(f"User: {profile['name']}")
        
        # This call will hit the cache
        profile_cached = github_tools.get_user_profile("octocat")
        
        # Check cache stats
        stats = github_tools.get_cache_stats()
        print(f"Cache hit rate: {stats.get('hit_rate', 0):.1f}%")
        
    finally:
        github_tools.close()