from __future__ import annotations

import os

from dotenv import load_dotenv
from openai import OpenAI


DEFAULT_MODEL = "gpt-5.5"
CAD_AGENT_API_KEY_ENV = "ABSCISSA_CAD_AGENT_API_KEY"
CAD_AGENT_MODEL_ENV = "ABSCISSA_CAD_AGENT_MODEL"
OPENAI_API_KEY_ENV = "OPENAI_API_KEY"
DISABLE_DOTENV_ENV = "ABSCISSA_DISABLE_DOTENV"


class CadAgentConfigurationError(RuntimeError):
    """Raised when the CAD assistant cannot run in the current environment."""


def load_project_env() -> None:
    if os.getenv(DISABLE_DOTENV_ENV) == "1":
        return
    load_dotenv()


def configured_model() -> str:
    load_project_env()
    return os.getenv(CAD_AGENT_MODEL_ENV, DEFAULT_MODEL)


def configured_api_key() -> str | None:
    load_project_env()
    return os.getenv(CAD_AGENT_API_KEY_ENV) or os.getenv(OPENAI_API_KEY_ENV)


def is_configured() -> bool:
    return bool(configured_api_key())


def build_cad_agent_instructions() -> str:
    return """
You are the Abscissa CAD assistant.

The current product is a lightweight 2D architectural floor-plan drafting board
for Abscissa CI: Construction Intelligence Aided Design. In this V1 chat, you
only answer questions and give drafting guidance. You do not directly edit the
floor plan yet.

Behavior:
- Be concise and practical.
- Favor professional residential drafting workflows.
- Keep property lines, setbacks, grids, columns, wall centerlines, wall
  thickness, openings, room labels, and dimensions conceptually separate.
- For Philippine residential context, assume metric dimensions, CHB walls,
  reinforced concrete structure, and a public to semi-public to private privacy
  gradient unless the user says otherwise.
- If a user asks you to modify the drawing, explain what should be done, but do
  not claim you applied changes.
""".strip()


def respond_to_cad_chat(message: str, *, model: str | None = None) -> str:
    api_key = configured_api_key()
    if not api_key:
        raise CadAgentConfigurationError(
            f"{CAD_AGENT_API_KEY_ENV} or {OPENAI_API_KEY_ENV} is required. "
            "Add it to .env, then restart abscissa-cad."
        )

    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model=model or configured_model(),
        instructions=build_cad_agent_instructions(),
        input=message,
    )
    return response.output_text.strip()
