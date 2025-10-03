from uuid import uuid4


# Currently, there are situations where we are not receiving and injected tool_call_id
# when we would expect it (more for tracing, but indicator we're off the beaten path).
# This method helps us work around that for now. Longer-term, we likely need to rework
# how we have the tool calling set up. Will revisit after LangChain v1 is available.
def generate_tool_call_id(prefix: str | None = "gh-call-"):
    """Generate a unique tool call identifier with optional prefix."""
    return f"{prefix}-{str(uuid4())}"
