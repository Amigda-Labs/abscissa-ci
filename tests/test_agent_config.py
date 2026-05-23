from abscissa_ci.agents.tile_agent import (
    DISABLE_DOTENV_ENV,
    OPENAI_API_KEY_ENV,
    TILE_ENGINEER_API_KEY_ENV,
    configured_api_key,
    configured_image_detail,
    configured_model,
)


def test_tile_engineer_api_key_takes_priority(monkeypatch):
    monkeypatch.setenv(DISABLE_DOTENV_ENV, "1")
    monkeypatch.setenv(TILE_ENGINEER_API_KEY_ENV, "tile-key")
    monkeypatch.setenv(OPENAI_API_KEY_ENV, "generic-key")

    assert configured_api_key() == "tile-key"


def test_openai_api_key_is_fallback(monkeypatch):
    monkeypatch.setenv(DISABLE_DOTENV_ENV, "1")
    monkeypatch.delenv(TILE_ENGINEER_API_KEY_ENV, raising=False)
    monkeypatch.setenv(OPENAI_API_KEY_ENV, "generic-key")

    assert configured_api_key() == "generic-key"


def test_default_model_and_image_detail(monkeypatch):
    monkeypatch.setenv(DISABLE_DOTENV_ENV, "1")
    monkeypatch.delenv("ABSCISSA_MODEL", raising=False)
    monkeypatch.delenv("ABSCISSA_IMAGE_DETAIL", raising=False)

    assert configured_model() == "gpt-5.2"
    assert configured_image_detail() == "high"
