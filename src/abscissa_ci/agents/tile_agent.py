from __future__ import annotations

import base64
import mimetypes
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from abscissa_ci.agents.shell_skills import build_tile_skill_shell_tool, tile_shell_skills
from abscissa_ci.models import FloorPlanExtraction, RectangleDraft, TileEstimateInput
from abscissa_ci.workflows.tile_estimation import estimate_tiles


DEFAULT_MODEL = "gpt-5.2"
DEFAULT_IMAGE_DETAIL = "high"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
TILE_ENGINEER_API_KEY_ENV = "ABSCISSA_TILE_ENGINEER_API_KEY"
OPENAI_API_KEY_ENV = "OPENAI_API_KEY"
DISABLE_DOTENV_ENV = "ABSCISSA_DISABLE_DOTENV"


class AgentConfigurationError(RuntimeError):
    """Raised when the agent runtime cannot be used in the current environment."""


def load_project_env() -> None:
    if os.getenv(DISABLE_DOTENV_ENV) == "1":
        return
    load_dotenv()


def configured_model() -> str:
    load_project_env()
    return os.getenv("ABSCISSA_MODEL", DEFAULT_MODEL)


def configured_image_detail() -> str:
    load_project_env()
    return os.getenv("ABSCISSA_IMAGE_DETAIL", DEFAULT_IMAGE_DETAIL)


def configured_api_key() -> str | None:
    load_project_env()
    return os.getenv(TILE_ENGINEER_API_KEY_ENV) or os.getenv(OPENAI_API_KEY_ENV)


def ensure_agent_runtime() -> tuple[Any, Any, Any]:
    api_key = configured_api_key()
    if not api_key:
        raise AgentConfigurationError(
            f"{TILE_ENGINEER_API_KEY_ENV} or {OPENAI_API_KEY_ENV} is required for image extraction. "
            "Use estimate-json to run deterministic calculations without the agent."
        )

    # The OpenAI Agents SDK reads OPENAI_API_KEY by default. Keep the project
    # variable first-class while still satisfying the SDK's default client.
    os.environ[OPENAI_API_KEY_ENV] = api_key

    try:
        from agents import Agent, Runner, function_tool
    except ImportError as exc:  # pragma: no cover - exercised only without dependency
        raise AgentConfigurationError(
            "The OpenAI Agents SDK is not installed. Run `uv sync` first."
        ) from exc

    return Agent, Runner, function_tool


def image_to_data_url(image_path: Path) -> str:
    suffix = image_path.suffix.lower()
    if suffix not in IMAGE_SUFFIXES:
        raise ValueError(f"Unsupported image type: {image_path.suffix}")

    mime_type = mimetypes.guess_type(image_path.name)[0] or "image/png"
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def build_extraction_prompt() -> str:
    return (
        "You are extracting draft floor-plan dimensions for Abscissa CI.\n"
        "The image should contain a rectilinear floor plan with visible metric dimensions.\n"
        "Extract rectangles only. Do not compute floor area or tile count.\n"
        "For each rectangle, return a name, length_m, width_m, operation, source_text, "
        "and confidence. Use operation='add' for included floor areas and operation='subtract' "
        "for voids or exclusions.\n"
        "If the footprint is L-shaped, T-shaped, or plus-shaped, decompose it into "
        "non-overlapping additive rectangles only. Do not also subtract the missing outside "
        "corner when you have already decomposed the shape into included floor rectangles. "
        "Use operation='subtract' only for true interior voids, openings, or exclusions inside "
        "an included floor area, or when you explicitly choose an outer-bounding-rectangle "
        "minus-void strategy. Do not mix both strategies for the same footprint. If a dimension "
        "is unclear, omit that rectangle and add a warning. All values are draft extraction data "
        "for later human evaluation."
    )


def build_shell_skill_prompt() -> str:
    skill_names = ", ".join(skill["name"] for skill in tile_shell_skills())
    return (
        f"The local shell environment exposes these Agent Skills: {skill_names}.\n"
        "When asked to compute area or tile counts inside an agent run, use those "
        "skills through the shell tool. The shell executor only permits the bundled "
        "tile skill scripts."
    )


async def extract_floor_plan_from_image(
    image_path: Path,
    model: str | None = None,
    use_shell_skills: bool = False,
) -> FloorPlanExtraction:
    Agent, Runner, _ = ensure_agent_runtime()
    instructions = build_extraction_prompt()
    tools = []
    if use_shell_skills:
        instructions += "\n\n" + build_shell_skill_prompt()
        tools.append(build_tile_skill_shell_tool())

    agent = Agent(
        name="Tile floor plan extraction",
        instructions=instructions,
        model=model or configured_model(),
        tools=tools,
        output_type=FloorPlanExtraction,
    )

    image_url = image_to_data_url(image_path)
    result = await Runner.run(
        agent,
        [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Extract the visible metric rectangular dimensions from this "
                            "floor plan. Return only structured draft extraction data."
                        ),
                    },
                    {
                        "type": "input_image",
                        "image_url": image_url,
                        "detail": configured_image_detail(),
                    },
                ],
            }
        ],
    )

    final_output = result.final_output
    if isinstance(final_output, FloorPlanExtraction):
        return final_output
    return FloorPlanExtraction.model_validate(final_output)


def build_area_tool(function_tool: Any) -> Any:
    @function_tool
    def compute_floor_area(rectangles: list[dict[str, Any]]) -> dict[str, Any]:
        """Compute room areas and total floor area from rectangular dimensions."""

        parsed = [RectangleDraft.model_validate(item) for item in rectangles]
        estimate_input = TileEstimateInput(rectangles=parsed, input_source="agent_tool")
        result = estimate_tiles(estimate_input)
        return result.model_dump(mode="json")

    return compute_floor_area


def build_tile_count_tool(function_tool: Any) -> Any:
    @function_tool
    def count_needed_tiles(total_floor_area_sqm: float, waste_percent: float = 10) -> dict[str, Any]:
        """Compute 600mm x 600mm base and order tile counts for a floor area."""

        estimate_input = TileEstimateInput(
            rectangles=[
                RectangleDraft(
                    name="Total floor area",
                    length_m=total_floor_area_sqm,
                    width_m=1,
                    source_text="Precomputed total floor area",
                )
            ],
            waste_percent=waste_percent,
            input_source="agent_tool",
        )
        result = estimate_tiles(estimate_input)
        return result.model_dump(mode="json")

    return count_needed_tiles


async def estimate_tiles_from_image(
    image_path: Path,
    model: str | None = None,
    use_shell_skills: bool = False,
):
    extraction = await extract_floor_plan_from_image(
        image_path,
        model=model,
        use_shell_skills=use_shell_skills,
    )

    estimate_input = TileEstimateInput(
        project_name=extraction.project_name or image_path.stem.replace("_", " ").title(),
        input_source="image",
        source_image_path=str(image_path),
        rectangles=extraction.rectangles,
        assumptions=[
            "Dimensions were extracted from a floor plan image by an agent.",
            "Extraction is draft-only and must be evaluated by a human reviewer.",
            *extraction.assumptions,
        ],
        warnings=extraction.warnings,
    )
    return estimate_tiles(estimate_input)
