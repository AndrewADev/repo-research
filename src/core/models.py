from langchain_core.prompts import PromptTemplate
from pydantic import (
    BaseModel,
)


class Prompt(BaseModel):
    content: str


class TemplatedPrompt(BaseModel):
    template: PromptTemplate
    keys: list[str]
