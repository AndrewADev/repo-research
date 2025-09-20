from pydantic import (
    BaseModel,
)


class ThreadedPrompt(BaseModel):
    """Prompt with follow-up questions"""
    prompt: str
    follow_ups: list[str]
