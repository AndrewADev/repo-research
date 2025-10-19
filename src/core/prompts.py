from langchain_core.prompts import PromptTemplate

from core.models import TemplatedPrompt, ThreadedPrompt

comprehensive_analysis = ThreadedPrompt(
    prompt="""
I need a comprehensive analysis of my currently starred repositories.
1. First, find the top 20 repositories I have starred with more than 5000 stars in total
2. For each of these repositories, analyze their recent activity
3. Provide a summary of which project seems to be most actively maintained
""",
    follow_ups=["Which of these project has the most active community?"],
)

run_diagnostic = ThreadedPrompt(
    prompt="""
I want to run diagnostics on various settings.
1. Please check the validity of the current GitHub token
2. Please check the rate limit status of the current GitHub token
""",
    follow_ups=[
        "Have any immediate issues been identified?",
    ],
)


topic_prompt = TemplatedPrompt(
    template=PromptTemplate.from_template(
        "I'm interested in learning about GitHub repositories "
        "related to: {topics}\n"
        "\n"
        "Please search for repositories using the "
        "search_repositories_by_topic tool with these parameters:\n"
        "- Topics: {topics}\n"
        "- Sort by: {sort}\n"
        "- Limit: {limit} results\n"
        "- Language: {language}\n"
        "- License: {license}\n"
        "- Minimum stars: {min_stars}\n"
        "- Maximum stars: {max_stars}\n"
        "- Pushed after: {pushed_after}\n"
        "- Archived filter: {archived}\n"
        "- Fork filter: {fork}\n"
        "\n"
        "Active filters:\n"
        "{filters_text}\n"
        "\n"
        "Please provide insights about the repositories you find, "
        "including their purpose, activity level, and why they might "
        "be interesting.\n"
    ),
    keys=[
        "topics",
        "sort",
        "limit",
        "language",
        "license",
        "min_stars",
        "max_stars",
        "pushed_after",
        "archived",
        "fork",
        "filters_text",
    ],
)


hotspot_analysis = TemplatedPrompt(
    template=PromptTemplate.from_template(
        "I need to identify maintenance hotspots in the repository: {repo_name}\n"
        "Please analyze the commit history with these parameters:\n"
        "- Analyze the last {days} days of commit history\n"
        "- Process up to {max_commits} commits\n"
        "- Only report files with at least {min_changes} changes\n"
        "{path_instruction}\n"
        "\n"
        "Focus on files with high churn (frequent changes with large diffs) as these "
        "are the most likely candidates for refactoring.\n"
        "Provide insights on the top hotspots and what they might indicate about "
        "the codebase structure."
    ),
    keys=["repo_name", "days", "max_commits", "min_changes", "path_instruction"],
)
