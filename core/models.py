from langchain_core.prompts import PromptTemplate
from pydantic import (
    BaseModel,
)


class ThreadedPrompt(BaseModel):
    """Prompt with follow-up questions"""

    prompt: str
    follow_ups: list[str]


class TemplatedPrompt(BaseModel):
    template: PromptTemplate
    keys: list[str]
