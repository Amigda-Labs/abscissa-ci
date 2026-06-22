from __future__ import annotations

import base64
import mimetypes
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from abscissa_ci.area.models import AreaReport, MeasurementBasis, PlanAreaExtraction
from abscissa_ci.area.validation import solve_area_takeoff


DEFAULT_MODEL = "gpt-5.5"
DEFAULT_IMAGE_DETAIL = "high"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
AREA_AGENT_API_KEY_ENV = "ABSCISSA_AREA_AGENT_API_KEY"
OPENAI_API_KEY_ENV = "OPENAI_API_KEY"
AREA_MODEL_ENV = "ABSCISSA_AREA_MODEL"
IMAGE_DETAIL_ENV = "ABSCISSA_IMAGE_DETAIL"
DISABLE_DOTENV_ENV = "ABSCISSA_DISABLE_DOTENV"


class AreaAgentConfigurationError(RuntimeError):
    """Raised when the Area Agent cannot run in the current environment."""


def load_project_env() -> None:
    if os.getenv(DISABLE_DOTENV_ENV) == "1":
        return
    load_dotenv()


def configured_model() -> str:
    load_project_env()
    return os.getenv(AREA_MODEL_ENV, DEFAULT_MODEL)


def configured_image_detail() -> str:
    load_project_env()
    return os.getenv(IMAGE_DETAIL_ENV, DEFAULT_IMAGE_DETAIL)


def configured_api_key() -> str | None:
    load_project_env()
    return os.getenv(AREA_AGENT_API_KEY_ENV) or os.getenv(OPENAI_API_KEY_ENV)


def ensure_agent_runtime() -> tuple[Any, Any]:
    api_key = configured_api_key()
    if not api_key:
        raise AreaAgentConfigurationError(
            f"{AREA_AGENT_API_KEY_ENV} or {OPENAI_API_KEY_ENV} is required for image analysis. "
            "Use validate-json to run deterministic area validation without the agent."
        )

    os.environ[OPENAI_API_KEY_ENV] = api_key

    try:
        from agents import Agent, Runner
    except ImportError as exc:  # pragma: no cover - exercised only without dependency
        raise AreaAgentConfigurationError(
            "The OpenAI Agents SDK is not installed. Run dependency installation first."
        ) from exc

    return Agent, Runner


def image_to_data_url(image_path: Path) -> str:
    suffix = image_path.suffix.lower()
    if suffix not in IMAGE_SUFFIXES:
        raise ValueError(f"Unsupported image type: {image_path.suffix}")

    mime_type = mimetypes.guess_type(image_path.name)[0] or "image/png"
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def build_area_extraction_prompt() -> str:
    return """
You are the Abscissa CI Area Agent.

Your only job is to extract draft area-takeoff geometry from architectural plan
images. Do not write a narrative estimate. Do not hide uncertainty. Do not
force a calculation when the plan does not support it.

Default measurement basis:
- Use net internal room area unless the user explicitly requests another basis.
- Net internal room area means measuring to the inside face of walls.
- Thick walls, exterior walls, and partitions are not room area under this
  basis.

Extraction requirements:
- Identify each room or included area separately.
- Record the room boundary basis: inside face, wall centerline, outside face,
  mixed, or unknown.
- Decompose non-rectangular rooms into additive and subtractive rectangular
  components where the plan supports that decomposition.
- Use subtract components for true negative spaces inside an included room:
  shafts, voids, courtyards, stairs, excluded openings, or other non-floor areas.
- Do not subtract missing outside corners if you already decomposed the room
  into included additive shapes.
- Preserve the visible source text for dimensions and area labels.
- Normalize dimensions into explicit units. If the unit is unclear, use
  "unknown" and ask a question.
- Include normalized image regions when you can identify them. Use values from
  0 to 1 for x_min, y_min, x_max, y_max.

Measurement sanity checks you must actively look for:
- Dimension chains that are explicitly shown on the same wall, axis, and
  measurement basis but do not add up.
- Room area labels that disagree with the dimensions shown.
- Dimensions whose unit or decimal placement is suspicious.
- Negative spaces larger than the containing room or component.
- Conflicting repeated dimensions for the same wall.
- Rooms whose boundaries are cut off, hidden, overlapped, or not closed.
- Scale bar, drawing scale, and dimension labels that appear inconsistent.
- Thick wall ambiguity where it is unclear whether dimensions are inside face,
  outside face, or centerline.
- Any room that would produce an implausibly tiny, huge, or negative net area.

Do not create an error-level consistency check by comparing an overall exterior
or footprint dimension against net internal room labels unless the drawing
explicitly says those dimensions share the same basis and are intended to sum.
Stepped plans, L-shaped plans, wall thickness, offsets, corridors, and partial
rows often make those comparisons invalid. In those cases, rely on the room
dimension labels for net area and put a warning only if the drawing is genuinely
ambiguous.

Return only structured extraction data matching the output schema. The local
Python harness will compute areas and decide whether the result can be trusted.
""".strip()


async def extract_area_takeoff_from_image(
    image_path: Path,
    *,
    requested_measurement_basis: MeasurementBasis = "net_internal_room_area",
    model: str | None = None,
) -> PlanAreaExtraction:
    Agent, Runner = ensure_agent_runtime()

    agent = Agent(
        name="Area Agent",
        instructions=build_area_extraction_prompt(),
        model=model or configured_model(),
        output_type=PlanAreaExtraction,
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
                            "Extract draft room area geometry from this architectural plan. "
                            f"Requested measurement basis: {requested_measurement_basis}. "
                            "Return structured extraction data only."
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
    if isinstance(final_output, PlanAreaExtraction):
        return final_output
    return PlanAreaExtraction.model_validate(final_output)


async def analyze_area_from_image(
    image_path: Path,
    *,
    requested_measurement_basis: MeasurementBasis = "net_internal_room_area",
    model: str | None = None,
) -> AreaReport:
    extraction = await extract_area_takeoff_from_image(
        image_path,
        requested_measurement_basis=requested_measurement_basis,
        model=model,
    )
    return solve_area_takeoff(
        extraction,
        requested_measurement_basis=requested_measurement_basis,
        source_image_path=str(image_path),
    )
