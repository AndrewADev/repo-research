"""Config endpoint exposing non-secret runtime settings to the SPA."""

from fastapi import APIRouter

from api.schemas import ConfigOut
from core.config import LLMProviderConfig, get_resolved_model_name

LANGUAGE_CHOICES: list[str] = [
    "Any",
    "Python",
    "JavaScript",
    "TypeScript",
    "Go",
    "Rust",
    "Java",
    "C++",
    "C",
    "Ruby",
    "PHP",
]

router = APIRouter()


@router.get("/config")
def get_app_config() -> ConfigOut:
    """Return the resolved provider/model and the language filter choices."""
    config = LLMProviderConfig()
    return ConfigOut(
        provider=config.llm_provider,
        model_name=get_resolved_model_name(None),
        languages=LANGUAGE_CHOICES,
    )
