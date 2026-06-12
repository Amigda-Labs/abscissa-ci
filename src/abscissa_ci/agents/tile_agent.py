from __future__ import annotations

import base64
import mimetypes
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from abscissa_ci.agents.shell_skills import build_tile_skill_shell_tool, tile_shell_skills
from abscissa_ci.calculators.dimension_stations import (
    filter_interval_matched_entries,
    survey_stations,
    validate_station_alignment,
    validate_station_usage,
    validate_survey,
)
from abscissa_ci.calculators.occupancy_geometry import (
    attach_inventory_labels,
    grid_to_polygons,
)
from abscissa_ci.calculators.polygon_geometry import (
    compute_polygon_areas,
    validate_dimension_coverage,
    validate_polygon_set,
)
from abscissa_ci.calculators.traverse_geometry import (
    traverse_derivation_notes,
    traverse_to_polygon,
)
from abscissa_ci.models import (
    DimensionSurvey,
    FloorPlanExtraction,
    OccupancyExtraction,
    PolygonDraft,
    RectangleDraft,
    TileEstimateInput,
    TraverseExtraction,
)
from abscissa_ci.workflows.tile_estimation import estimate_tiles


DEFAULT_MODEL = "gpt-5.2"
DEFAULT_IMAGE_DETAIL = "high"
MAX_EXTRACTION_ATTEMPTS = 3
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


def configured_reasoning_effort() -> str | None:
    """Optional reasoning effort; not every model accepts the parameter."""

    load_project_env()
    return os.getenv("ABSCISSA_REASONING_EFFORT") or None


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


def build_survey_prompt() -> str:
    return (
        "You are surveying a floor plan drawing for Abscissa CI. This is a perception "
        "pass only: report what is printed on the drawing. Do NOT describe, guess, or "
        "reason about the building shape, and do not compute anything.\n"
        "1. Read the overall bounding dimensions: the outermost horizontal dimension "
        "line is the plan's total width (bounding_width_m) and the outermost vertical "
        "dimension line is its total height (bounding_height_m).\n"
        "2. List EVERY dimension label printed on the drawing as an entry, with "
        "source_text quoting the printed text exactly, including duplicates. Ignore "
        "the scale bar and title block.\n"
        "3. For each entry, report orientation: 'horizontal' when the dimension line "
        "runs left-right (it measures a width), 'vertical' when it runs up-down (it "
        "measures a height).\n"
        "4. For each entry, report side: where the dimension line is drawn relative "
        "to the building outline - top, bottom, left, right, or interior.\n"
        "5. Group the labels into dimension chains: one chain per dimension lane (a "
        "row or column of dimension lines connected by shared extension lines). A "
        "chain contains ONLY the segments drawn in that one lane - never merge "
        "labels from different lanes into one chain, even when their values look "
        "related. List each chain's segments in geometric order - left-to-right "
        "for horizontal chains, top-to-bottom for vertical chains. Quote each "
        "segment's printed text in source_text; when a run between two extension "
        "lines inside the lane has no printed label, include it as a segment with "
        "source_text null in its correct position.\n"
        "6. Report each chain's anchoring. starts_at_outline_edge=true when the "
        "chain's first extension line (its left end for a horizontal chain, its "
        "top end for a vertical chain) aligns with the outline's extreme position "
        "on that axis - the leftmost point of the footprint for horizontal, the "
        "topmost for vertical. ends_at_outline_edge=true when its last extension "
        "line aligns with the opposite extreme (rightmost / bottommost). Set "
        "spans_full_extent=true only when both are true. The lane itself may be "
        "drawn anywhere on the page; what matters is which positions its "
        "extension lines mark on the footprint.\n"
        "7. Cross-check before answering: a full-extent chain's segments (including "
        "gaps) must sum to the overall dimension on its axis (for example "
        "5.00 + 4.00 + 7.00 = 16.00). If a chain does not sum, re-read the digits; "
        "record any remaining discrepancy in notes."
    )


def build_traverse_prompt() -> str:
    return (
        "You are tracing the floor-plan boundary for Abscissa CI as a closed "
        "surveyor's traverse, using ONLY the dimension survey already established in "
        "this conversation. Do not compute floor area or tile count.\n"
        "1. Output each included floor outline as one traverse: an ordered list of "
        "moves, one move per boundary segment. Each move has a compass direction - "
        "E (right), N (up), W (left), S (down) - and a length in meters. You never "
        "output coordinates; they are derived from your moves deterministically.\n"
        "2. Start at the bottom-left corner of the footprint and walk "
        "counter-clockwise, so the first move heads E along the bottom edge.\n"
        "3. Every move length must come from the survey: either copy one printed "
        "label into source_text exactly as surveyed, or derive the length by chain "
        "arithmetic over printed labels and state that arithmetic in derivation "
        "(for example '16.00 - 5.00 - 7.00') with source_text null. Never estimate "
        "from pixels and never invent a source_text.\n"
        "4. Use each printed segment label for exactly one move. Horizontal labels "
        "can only measure E or W moves; vertical labels only N or S moves.\n"
        "5. Check closure before answering, like closing a survey traverse: the E "
        "move lengths must sum to exactly the same total as the W moves, and the N "
        "moves to the same total as the S moves. The leftmost-to-rightmost extent of "
        "the walk must equal bounding_width_m and the bottom-to-top extent must "
        "equal bounding_height_m. If any check fails, your segment lengths are "
        "wrong: re-read the chains and fix them before answering.\n"
        "6. Every corner of your walk must land on the station grid defined by the "
        "surveyed dimension chains - the extension-line positions where dimension "
        "segments start and end. A corner between stations means you attached a "
        "segment to the wrong part of the boundary.\n"
        "7. Copy bounding_width_m and bounding_height_m from the survey onto the "
        "outer floor traverse.\n"
        "8. Use operation='add' for included floor areas and operation='subtract' "
        "for interior voids, openings, or exclusions. A void traverse must lie "
        "inside an included floor traverse, and included traverses must not overlap.\n"
        "9. Fall back to add/subtract rectangles only when a confident traverse is "
        "impossible, and never represent the same floor region both ways. If a "
        "dimension is unclear, omit that shape and add a warning. All values are "
        "draft extraction data for later human evaluation.\n"
        "\n"
        "Worked example: an L-shaped footprint, 12.00 m wide and 9.00 m tall "
        "overall, with a top chain of 7.00 + 5.00 and a right chain of 5.00 + 4.00. "
        "Starting at the bottom-left corner and walking counter-clockwise the moves "
        "are: E 12.00, N 5.00, W 5.00, N 4.00, W 7.00, S 9.00. Closure: east total "
        "12.00 equals west total 5.00 + 7.00; north total 5.00 + 4.00 equals south "
        "total 9.00."
    )


def build_shell_skill_prompt() -> str:
    skill_names = ", ".join(skill["name"] for skill in tile_shell_skills())
    return (
        f"The local shell environment exposes these Agent Skills: {skill_names}.\n"
        "When asked to compute area or tile counts inside an agent run, use those "
        "skills through the shell tool. The shell executor only permits the bundled "
        "tile skill scripts."
    )


def validate_traverse_extraction(
    extraction: TraverseExtraction,
    dimension_inventory: list[str],
    survey: DimensionSurvey | None = None,
) -> tuple[list[PolygonDraft], list[str]]:
    """Convert traverses to polygons and run the deterministic geometry checks.

    Returns every successfully closed polygon (so the reviewer can see the
    attempted shape even when other checks fail) plus the full error list.
    """

    polygons: list[PolygonDraft] = []
    errors: list[str] = []
    for traverse in extraction.traverses:
        polygon, traverse_errors = traverse_to_polygon(traverse)
        if polygon is None:
            errors.extend(traverse_errors)
            continue
        polygons.append(polygon)

    zones = compute_polygon_areas(polygons)
    errors.extend(error for zone in zones for error in zone.errors)
    valid_drafts = [draft for draft, zone in zip(polygons, zones) if zone.is_valid]
    errors.extend(validate_polygon_set(valid_drafts))
    errors.extend(validate_dimension_coverage(dimension_inventory, valid_drafts))
    if survey is not None:
        errors.extend(validate_station_alignment(valid_drafts, survey))
    return polygons, errors


def build_correction_prompt(errors: list[str]) -> str:
    listed = "\n".join(f"- {error}" for error in errors)
    return (
        "Deterministic traverse validation found these errors in your extraction:\n"
        f"{listed}\n"
        "Look at the floor plan image again and redo the traverse. A misclosure "
        "tells you which axis is wrong and by how much; re-read the dimension "
        "chains on that axis. Every printed label from the survey must be used by "
        "exactly one move or be an overall bounding dimension. Return the corrected "
        "extraction."
    )


def build_occupancy_prompt() -> str:
    return (
        "You are classifying station-grid cells of a floor plan for Abscissa CI. "
        "The printed dimension chains define stations; the grid cells between "
        "stations are listed in the request. This is a perception task: look at "
        "the drawing and report, for every cell, whether the building footprint "
        "(the floor area enclosed by the thick outline walls) covers it.\n"
        "1. Go cell by cell, in the order the request lists them. For each cell, "
        "locate its region on the drawing using its x and y ranges, decide floor "
        "or not, and put every floor cell into occupied_cells as its (row, col) "
        "pair. Cells outside the footprint, or inside an interior void, "
        "courtyard, or opening, are not occupied.\n"
        "2. Then state the same result a second time as occupied_rows: one list "
        "per grid row, top-to-bottom; within a row, one boolean per column, "
        "left-to-right. The two descriptions are cross-checked cell by cell and "
        "must agree exactly.\n"
        "3. The stations align with the footprint's corners, so each cell is "
        "either fully floor or fully not. If a cell looks only partially covered, "
        "first re-check that you located it correctly using its exact x and y "
        "ranges; if it still looks partial, report it in "
        "partially_covered_cells.\n"
        "4. Do not output coordinates and do not compute area or tile counts. All "
        "values are draft extraction data for later human evaluation."
    )


def format_grid_request(x_stations: list[float], y_stations: list[float]) -> str:
    columns = len(x_stations) - 1
    rows = len(y_stations) - 1
    lines = [
        f"The surveyed dimension chains divide the plan into a grid of {rows} "
        f"row(s) by {columns} column(s). Row 1 is the TOP strip of the drawing; "
        f"column 1 is the LEFTMOST strip. The cells are:",
    ]
    for row in range(rows):
        y_low = y_stations[rows - row - 1]
        y_high = y_stations[rows - row]
        for col in range(columns):
            lines.append(
                f"- cell (row {row + 1}, col {col + 1}): x from "
                f"{x_stations[col]:g} to {x_stations[col + 1]:g} m, y from "
                f"{y_low:g} to {y_high:g} m"
            )
    lines.append(
        "Inspect each cell's region on the drawing in this order. Report every "
        "floor-covered cell in occupied_cells, then repeat the same answer as "
        "the occupied_rows boolean matrix; both must agree exactly."
    )
    return "\n".join(lines)


def build_occupancy_correction_prompt(errors: list[str]) -> str:
    listed = "\n".join(f"- {error}" for error in errors)
    return (
        "Deterministic validation of the footprint derived from your cell "
        "occupancy found these errors:\n"
        f"{listed}\n"
        "Look at the floor plan image again and re-decide which grid cells the "
        "footprint covers. An unaccounted printed dimension means an edge of that "
        "length is missing from your footprint; a bounding mismatch means your "
        "occupancy does not reach the outline's extremes. Return the corrected "
        "occupancy grid."
    )


def occupancy_consistency_errors(
    extraction: OccupancyExtraction, rows: int, columns: int
) -> list[str]:
    """The cell list and the boolean matrix must describe the same cells."""

    errors: list[str] = []
    listed: set[tuple[int, int]] = set()
    for cell in extraction.occupied_cells:
        if not (1 <= cell.row <= rows and 1 <= cell.col <= columns):
            errors.append(
                f"Occupied cell (row {cell.row}, col {cell.col}) is outside the "
                f"{rows}x{columns} station grid."
            )
            continue
        listed.add((cell.row, cell.col))

    matrix = {
        (row_index + 1, col_index + 1)
        for row_index, row in enumerate(extraction.occupied_rows)
        for col_index, occupied in enumerate(row)
        if occupied
    }
    for row, col in sorted(listed - matrix):
        errors.append(
            f"Cell (row {row}, col {col}) is in occupied_cells but false in "
            "occupied_rows; the two descriptions must agree - re-check that cell "
            "against the drawing."
        )
    for row, col in sorted(matrix - listed):
        errors.append(
            f"Cell (row {row}, col {col}) is true in occupied_rows but missing "
            "from occupied_cells; the two descriptions must agree - re-check that "
            "cell against the drawing."
        )
    return errors


def validate_occupancy_extraction(
    extraction: OccupancyExtraction,
    dimension_inventory: list[str],
    x_stations: list[float],
    y_stations: list[float],
    survey: DimensionSurvey,
) -> tuple[list[PolygonDraft], list[str]]:
    """Derive polygons from the occupancy grid and run the geometry checks."""

    errors = occupancy_consistency_errors(
        extraction, rows=len(y_stations) - 1, columns=len(x_stations) - 1
    )
    # A partially covered cell contradicts the station grid: stations sit on
    # footprint corners, so every cell is fully floor or fully not. Either the
    # grid is wrong or the cell was mislocated; both make the draft untrustworthy.
    for cell in extraction.partially_covered_cells:
        errors.append(
            f"Cell (row {cell.row}, col {cell.col}) was reported as partially "
            "covered, which cannot happen on a correct station grid. Re-locate "
            "the cell using its exact x and y ranges; if it still looks partial, "
            "the dimension survey is wrong."
        )
    if errors:
        return [], errors

    polygons, errors = grid_to_polygons(x_stations, y_stations, extraction.occupied_rows)
    if errors:
        return polygons, errors

    attach_inventory_labels(polygons, dimension_inventory)
    adds = [polygon for polygon in polygons if polygon.operation == "add"]
    if len(adds) == 1:
        if survey.bounding_width_m is not None:
            adds[0].bounding_width_m = survey.bounding_width_m
        if survey.bounding_height_m is not None:
            adds[0].bounding_height_m = survey.bounding_height_m

    zones = compute_polygon_areas(polygons)
    errors.extend(error for zone in zones for error in zone.errors)
    valid_drafts = [draft for draft, zone in zip(polygons, zones) if zone.is_valid]
    errors.extend(validate_polygon_set(valid_drafts))
    errors.extend(validate_station_usage(valid_drafts, x_stations, y_stations))
    # A printed dimension may measure a station interval (a void margin, a
    # recess offset) rather than a boundary edge; the grid accounts for those.
    unexplained = filter_interval_matched_entries(
        dimension_inventory, x_stations, y_stations
    )
    errors.extend(validate_dimension_coverage(unexplained, valid_drafts))
    return polygons, errors


def split_downstream_inventory(
    inventory: list[str],
    polygons: list[PolygonDraft],
    x_stations: list[float],
    y_stations: list[float],
) -> tuple[list[str], list[str]]:
    """Split the inventory into entries the workflow can re-verify against the
    polygons (edge labels, bounding dims) and entries that only the station
    grid accounts for (feature positions like void margins)."""

    attached_pool = [
        label.source_text.strip()
        for polygon in polygons
        for label in polygon.edge_labels
        if label.source_text
    ]
    verifiable: list[str] = []
    positioned: list[str] = []
    for entry in inventory:
        text = entry.strip()
        if text in attached_pool:
            attached_pool.remove(text)
            verifiable.append(entry)
        elif not filter_interval_matched_entries([entry], x_stations, y_stations):
            positioned.append(entry)
        else:
            verifiable.append(entry)
    return verifiable, positioned


def survey_inventory(survey: DimensionSurvey) -> list[str]:
    return [entry.source_text for entry in survey.entries]


def format_station_grid(survey: DimensionSurvey) -> str:
    """Spell out the deterministic station grid so the assembly pass can pick
    corners from it instead of re-deriving chain arithmetic."""

    x_stations, y_stations = survey_stations(survey)
    if x_stations is None and y_stations is None:
        return ""

    def fmt(stations: list[float] | None) -> str:
        if stations is None:
            return "not determined"
        return ", ".join(f"{station:g}" for station in stations)

    return (
        f"Station grid computed from your survey - x stations: {fmt(x_stations)} m; "
        f"y stations: {fmt(y_stations)} m (0 is the outline's minimum on each axis). "
        "Every corner of your walk must land on a station of each determined axis, "
        "and every move length must equal the distance between two stations on its "
        "axis."
    )


def assemble_floor_plan_extraction(
    extraction: TraverseExtraction,
    survey: DimensionSurvey,
    polygons: list[PolygonDraft],
    validation_errors: list[str] | None = None,
) -> FloorPlanExtraction:
    assumptions = [*extraction.assumptions]
    for traverse in extraction.traverses:
        assumptions.extend(traverse_derivation_notes(traverse))
    return FloorPlanExtraction(
        project_name=extraction.project_name,
        rectangles=extraction.rectangles,
        polygons=polygons,
        dimension_inventory=survey_inventory(survey),
        validation_errors=list(validation_errors or []),
        assumptions=assumptions,
        warnings=list(extraction.warnings),
    )


def _user_message(text: str, image_url: str) -> dict[str, Any]:
    return {
        "role": "user",
        "content": [
            {"type": "input_text", "text": text},
            {
                "type": "input_image",
                "image_url": image_url,
                "detail": configured_image_detail(),
            },
        ],
    }


async def extract_floor_plan_from_image(
    image_path: Path,
    model: str | None = None,
    use_shell_skills: bool = False,
) -> FloorPlanExtraction:
    Agent, Runner, _ = ensure_agent_runtime()

    traverse_instructions = build_traverse_prompt()
    tools = []
    if use_shell_skills:
        traverse_instructions += "\n\n" + build_shell_skill_prompt()
        tools.append(build_tile_skill_shell_tool())

    agent_kwargs: dict[str, Any] = {}
    reasoning_effort = configured_reasoning_effort()
    if reasoning_effort:
        from agents import ModelSettings
        from openai.types.shared import Reasoning

        agent_kwargs["model_settings"] = ModelSettings(reasoning=Reasoning(effort=reasoning_effort))

    model_name = model or configured_model()
    survey_agent = Agent(
        name="Floor plan dimension survey",
        instructions=build_survey_prompt(),
        model=model_name,
        output_type=DimensionSurvey,
        **agent_kwargs,
    )
    traverse_agent = Agent(
        name="Floor plan boundary traverse",
        instructions=traverse_instructions,
        model=model_name,
        tools=tools,
        output_type=TraverseExtraction,
        **agent_kwargs,
    )

    image_url = image_to_data_url(image_path)

    # A failed assembly round usually means the survey itself was wrong (chains
    # grouped or ordered incorrectly), so one full re-survey round is allowed.
    extraction: FloorPlanExtraction | None = None
    prior_round_errors: list[str] = []
    for _ in range(2):
        # Pass A: perception only. The survey fixes the dimension inventory and
        # the station grid before any shape reasoning, so the assembly pass can
        # neither drop inconvenient labels nor invent geometry.
        survey_result, survey = await _run_survey(
            Runner, survey_agent, image_url, prior_round_errors
        )
        inventory = survey_inventory(survey)
        x_stations, y_stations = survey_stations(survey)

        # Pass B: assembly. With the station grid fully determined on both
        # axes, the model only classifies cells as floor or not - pure
        # perception - and the polygon is derived deterministically. The
        # traverse path remains the fallback for under-dimensioned drawings.
        if x_stations is not None and y_stations is not None:
            occupancy_agent = Agent(
                name="Floor plan cell occupancy",
                instructions=build_occupancy_prompt(),
                model=model_name,
                output_type=OccupancyExtraction,
                **agent_kwargs,
            )
            extraction = await _run_occupancy_assembly(
                Runner,
                occupancy_agent,
                survey_result,
                survey,
                inventory,
                x_stations,
                y_stations,
                image_url,
            )
        else:
            extraction = await _run_traverse_assembly(
                Runner, traverse_agent, survey_result, survey, inventory, image_url
            )

        if not extraction.validation_errors:
            return extraction
        prior_round_errors = extraction.validation_errors

    return extraction


async def _run_survey(
    Runner: Any,
    survey_agent: Any,
    image_url: str,
    prior_round_errors: list[str],
) -> tuple[Any, DimensionSurvey]:
    request = (
        "Survey every printed dimension on this floor plan: overall bounding "
        "dimensions, each label with its orientation and side, and the dimension "
        "chains lane by lane."
    )
    if prior_round_errors:
        listed = "\n".join(f"- {error}" for error in prior_round_errors)
        request += (
            "\nA previous extraction round failed deterministic validation with "
            "these errors:\n"
            f"{listed}\n"
            "The dimension chains were probably grouped into the wrong lanes or "
            "ordered incorrectly. Survey the drawing again with fresh eyes."
        )

    survey_result: Any = None
    survey = DimensionSurvey()
    conversation: list[Any] = [_user_message(request, image_url)]
    for attempt in range(1, MAX_EXTRACTION_ATTEMPTS + 1):
        survey_result = await Runner.run(survey_agent, conversation)
        survey_output = survey_result.final_output
        survey = (
            survey_output
            if isinstance(survey_output, DimensionSurvey)
            else DimensionSurvey.model_validate(survey_output)
        )

        survey_errors = validate_survey(survey)
        if not survey_errors or attempt == MAX_EXTRACTION_ATTEMPTS:
            break

        listed = "\n".join(f"- {error}" for error in survey_errors)
        conversation = survey_result.to_input_list()
        conversation.append(
            _user_message(
                "Deterministic checks found these inconsistencies in your survey:\n"
                f"{listed}\n"
                "Re-read the drawing and return a corrected survey. Every label "
                "belongs to exactly one chain in its own lane, in geometric order, "
                "or is an overall bounding dimension.",
                image_url,
            )
        )

    return survey_result, survey


async def _run_occupancy_assembly(
    Runner: Any,
    occupancy_agent: Any,
    survey_result: Any,
    survey: DimensionSurvey,
    inventory: list[str],
    x_stations: list[float],
    y_stations: list[float],
    image_url: str,
) -> FloorPlanExtraction:
    conversation = survey_result.to_input_list()
    conversation.append(_user_message(format_grid_request(x_stations, y_stations), image_url))

    extraction = OccupancyExtraction()
    polygons: list[PolygonDraft] = []
    errors: list[str] = []
    for attempt in range(1, MAX_EXTRACTION_ATTEMPTS + 1):
        result = await Runner.run(occupancy_agent, conversation)
        final_output = result.final_output
        if isinstance(final_output, OccupancyExtraction):
            extraction = final_output
        else:
            extraction = OccupancyExtraction.model_validate(final_output)

        polygons, errors = validate_occupancy_extraction(
            extraction, inventory, x_stations, y_stations, survey
        )
        if not errors:
            if attempt > 1:
                extraction.warnings.append(
                    f"Extraction needed {attempt - 1} validation-feedback "
                    f"correction{'s' if attempt > 2 else ''} before the geometry passed."
                )
            break

        if attempt == MAX_EXTRACTION_ATTEMPTS:
            extraction.warnings.append(
                f"Extraction geometry still failed validation after "
                f"{MAX_EXTRACTION_ATTEMPTS} attempts."
            )
            break

        conversation = result.to_input_list()
        conversation.append(
            _user_message(build_occupancy_correction_prompt(errors), image_url)
        )

    # Entries that only position features (void margins, recess offsets) are
    # accounted for by the station grid; the workflow's coverage re-check can
    # only verify edge labels and bounding dims, so split them out.
    verifiable_inventory, positioned = split_downstream_inventory(
        inventory, polygons, x_stations, y_stations
    )
    assumptions = [
        "Footprint was derived deterministically from the dimension-chain "
        "station grid and the agent's cell occupancy classification.",
        "Station grid: x stations "
        + ", ".join(f"{station:g}" for station in x_stations)
        + " m; y stations "
        + ", ".join(f"{station:g}" for station in y_stations)
        + " m.",
    ]
    if positioned:
        assumptions.append(
            "Printed dimensions accounted for as station intervals (feature "
            "positions): " + ", ".join(positioned) + "."
        )
    return FloorPlanExtraction(
        project_name=extraction.project_name,
        polygons=polygons,
        dimension_inventory=verifiable_inventory,
        validation_errors=errors,
        assumptions=[*assumptions, *extraction.assumptions],
        warnings=list(extraction.warnings),
    )


async def _run_traverse_assembly(
    Runner: Any,
    traverse_agent: Any,
    survey_result: Any,
    survey: DimensionSurvey,
    inventory: list[str],
    image_url: str,
) -> FloorPlanExtraction:
    station_grid = format_station_grid(survey)

    conversation = survey_result.to_input_list()
    assembly_request = (
        "Now trace the boundary as a closed traverse using only the surveyed "
        "dimensions. Every move length must cite a surveyed label or state its "
        "chain derivation."
    )
    if station_grid:
        assembly_request += "\n" + station_grid
    conversation.append(_user_message(assembly_request, image_url))

    extraction = TraverseExtraction()
    polygons: list[PolygonDraft] = []
    errors: list[str] = []
    for attempt in range(1, MAX_EXTRACTION_ATTEMPTS + 1):
        result = await Runner.run(traverse_agent, conversation)
        final_output = result.final_output
        if isinstance(final_output, TraverseExtraction):
            extraction = final_output
        else:
            extraction = TraverseExtraction.model_validate(final_output)

        polygons, errors = validate_traverse_extraction(extraction, inventory, survey)
        if not errors:
            if attempt > 1:
                extraction.warnings.append(
                    f"Extraction needed {attempt - 1} validation-feedback "
                    f"correction{'s' if attempt > 2 else ''} before the geometry passed."
                )
            return assemble_floor_plan_extraction(extraction, survey, polygons)

        if attempt == MAX_EXTRACTION_ATTEMPTS:
            break

        conversation = result.to_input_list()
        correction = build_correction_prompt(errors)
        if station_grid:
            correction += "\n" + station_grid
        conversation.append(_user_message(correction, image_url))

    extraction.warnings.append(
        f"Extraction geometry still failed validation after {MAX_EXTRACTION_ATTEMPTS} attempts."
    )
    return assemble_floor_plan_extraction(
        extraction, survey, polygons, validation_errors=errors
    )


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
        polygons=extraction.polygons,
        dimension_inventory=extraction.dimension_inventory,
        validation_errors=extraction.validation_errors,
        assumptions=[
            "Dimensions were extracted from a floor plan image by an agent.",
            "Extraction is draft-only and must be evaluated by a human reviewer.",
            *extraction.assumptions,
        ],
        warnings=extraction.warnings,
    )
    return estimate_tiles(estimate_input)
