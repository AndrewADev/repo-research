from core.models import ThreadedPrompt


comprehensive_analysis=ThreadedPrompt(
  prompt="""
I need a comprehensive analysis of my currently starred repositories.
1. First, find the top 20 repositories I have starred with more than 5000 stars in total
2. For each of these repositories, analyze their recent activity
3. Provide a summary of which framework seems to be most actively maintained
""",
  follow_ups=[
    "Which of these frameworks has the most active community?"
  ]

)

run_diagnostic=ThreadedPrompt(
  # prompt="Can you help me determine the current rate_limit state of the current token?",
  prompt="""
I want to run diagnostics on various settings.
1. Please check the rate limit status of the current token
""",
  follow_ups=[
    "Have any immediate issues been identified?",
  ]
)