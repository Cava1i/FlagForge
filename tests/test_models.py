from pydantic_ai.models.openai import OpenAIResponsesModel

from backend.config import Settings
from backend.models import resolve_model


def test_openai_provider_uses_responses_api_model():
    settings = Settings(openai_base_url="https://api.psydo.top", openai_api_key="sk-test")

    model = resolve_model("openai/gpt-5.5", settings)

    assert isinstance(model, OpenAIResponsesModel)
