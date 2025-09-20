import os
from dotenv import load_dotenv

from tools.github_adapter import create_graph



# Load environment variables
load_dotenv()

# Configure LLM provider
provider = os.getenv("LLM_PROVIDER", "ollama")  # Default to ollama
anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
model_name = os.getenv("MODEL_NAME", None)

# Create the graph
graph = create_graph(
    provider=provider,
    anthropic_api_key=anthropic_api_key,
    ollama_base_url=ollama_base_url,
    model=model_name
)

# Configure the execution
config = {"configurable": {"thread_id": "example_chat"}}

# analysis_prompt = """
# I need a comprehensive analysis of the most popular AI framework repositories.
# 1. First, find the top 5 AI framework repositories with more than 10000 stars
# 2. For each of these repositories, analyze their recent activity
# 3. Provide a summary of which framework seems to be most actively maintained
# """

analysis_prompt = """
I need a comprehensive analysis of my currently starred repositories.
1. First, find the top 20 repositories I have starred with more than 5000 stars in total
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