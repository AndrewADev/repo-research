import os
from dotenv import load_dotenv

from tools.github_adapter import create_graph



# Load environment variables
load_dotenv()

# Create the graph
graph = create_graph(os.getenv("ANTHROPIC_API_KEY"))

# Configure the execution
config = {"configurable": {"thread_id": "example_chat"}}

analysis_prompt = """
I need a comprehensive analysis of the most popular AI framework repositories.
1. First, find the top 5 AI framework repositories with more than 10000 stars
2. For each of these repositories, analyze their recent activity
3. Provide a summary of which framework seems to be most actively maintained
"""

# Run the analysis
try:
    # Initialize with our first message
    events = graph.stream(
        {"messages": [("user", analysis_prompt)]},
        config,
        stream_mode="values"
    )
    
    # Print each event as it occurs
    for event in events:
        if "messages" in event:
            last_message = event["messages"][-1]
            print(f"Step output: {last_message.content}\n")
            
except Exception as e:
    print(f"Error during analysis: {str(e)}")
    
# We can continue the conversation by streaming again with new input
follow_up = "Which of these frameworks has the most active community?"

events = graph.stream(
    {"messages": [("user", follow_up)]},
    config,
    stream_mode="values"
)

for event in events:
    if "messages" in event:
        last_message = event["messages"][-1]
        print(f"Follow-up response: {last_message.content}\n")