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
        "I'm interested in learning about GitHub repositories. "
        "I was wondering if you could help find recently active repositories "
        "related to: {topics} \n"
        "If any of the topics are programming languages, then please filter to only "
        "repositories using that language. \n"
        "Please filter to only repositories that were pushed to within the last "
        "30 days. \n"
    ),
    keys=["topics"],
)
