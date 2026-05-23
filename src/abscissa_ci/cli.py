from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from abscissa_ci.agents.tile_agent import AgentConfigurationError, IMAGE_SUFFIXES, estimate_tiles_from_image
from abscissa_ci.models import TileEstimateInput
from abscissa_ci.reporting.markdown import render_tile_estimate_markdown
from abscissa_ci.workflows.tile_estimation import estimate_tiles


app = typer.Typer(help="Abscissa CI tile area and tile count workflows.")


def read_json_input(path: Path) -> TileEstimateInput:
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"Invalid JSON input: {exc}") from exc

    try:
        return TileEstimateInput.model_validate(payload)
    except ValidationError as exc:
        raise typer.BadParameter(str(exc)) from exc


def output_paths(source_path: Path) -> tuple[Path, Path]:
    return (
        source_path.with_name(f"{source_path.stem}.tile_estimate.json"),
        source_path.with_name(f"{source_path.stem}.tile_estimate.md"),
    )


def write_outputs(source_path: Path, result) -> tuple[Path, Path]:
    json_path, markdown_path = output_paths(source_path)
    json_path.write_text(result.model_dump_json(indent=2) + "\n")
    markdown_path.write_text(render_tile_estimate_markdown(result))
    return json_path, markdown_path


def estimate_json_file(input_path: Path):
    estimate_input = read_json_input(input_path)
    if estimate_input.input_source == "unknown":
        estimate_input.input_source = "json"
    return estimate_tiles(estimate_input)


@app.command()
def estimate(
    input_path: Annotated[Path, typer.Argument(help="Floor-plan image or JSON rectangle input.")],
    model: Annotated[str | None, typer.Option(help="OpenAI model override. Defaults to ABSCISSA_MODEL or gpt-5.2.")] = None,
    use_shell_skills: Annotated[
        bool,
        typer.Option(
            "--use-shell-skills/--no-shell-skills",
            help="Expose local Agent Skills through ShellTool. Requires a model that supports shell tools.",
        ),
    ] = False,
):
    """Estimate floor area and 600x600 tile count for one image or JSON file."""

    if not input_path.exists():
        raise typer.BadParameter(f"Input does not exist: {input_path}")

    try:
        if input_path.suffix.lower() == ".json":
            result = estimate_json_file(input_path)
        elif input_path.suffix.lower() in IMAGE_SUFFIXES:
            result = asyncio.run(
                estimate_tiles_from_image(
                    input_path,
                    model=model,
                    use_shell_skills=use_shell_skills,
                )
            )
        else:
            raise typer.BadParameter(
                f"Unsupported input type: {input_path.suffix}. Use an image or JSON file."
            )
    except AgentConfigurationError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc

    json_path, markdown_path = write_outputs(input_path, result)
    typer.echo(f"Wrote {json_path}")
    typer.echo(f"Wrote {markdown_path}")


@app.command("estimate-json")
def estimate_json(
    input_path: Annotated[Path, typer.Argument(help="JSON rectangle input.")],
):
    """Run deterministic tile calculations from JSON without the image agent."""

    if not input_path.exists():
        raise typer.BadParameter(f"Input does not exist: {input_path}")
    result = estimate_json_file(input_path)
    json_path, markdown_path = write_outputs(input_path, result)
    typer.echo(f"Wrote {json_path}")
    typer.echo(f"Wrote {markdown_path}")


@app.command()
def batch(
    folder: Annotated[Path, typer.Argument(help="Folder containing floor-plan images.")],
    model: Annotated[str | None, typer.Option(help="OpenAI model override. Defaults to ABSCISSA_MODEL or gpt-5.2.")] = None,
    use_shell_skills: Annotated[
        bool,
        typer.Option(
            "--use-shell-skills/--no-shell-skills",
            help="Expose local Agent Skills through ShellTool. Requires a model that supports shell tools.",
        ),
    ] = False,
):
    """Estimate tile counts for every supported image in a folder."""

    if not folder.exists() or not folder.is_dir():
        raise typer.BadParameter(f"Folder does not exist: {folder}")

    images = sorted(path for path in folder.iterdir() if path.suffix.lower() in IMAGE_SUFFIXES)
    if not images:
        typer.echo(f"No supported images found in {folder}")
        raise typer.Exit(code=0)

    failures = 0
    for image_path in images:
        try:
            result = asyncio.run(
                estimate_tiles_from_image(
                    image_path,
                    model=model,
                    use_shell_skills=use_shell_skills,
                )
            )
            json_path, markdown_path = write_outputs(image_path, result)
            typer.echo(f"{image_path.name}: wrote {json_path.name}, {markdown_path.name}")
        except AgentConfigurationError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=2) from exc
        except Exception as exc:  # pragma: no cover - defensive CLI behavior
            failures += 1
            typer.echo(f"{image_path.name}: failed: {exc}", err=True)

    if failures:
        raise typer.Exit(code=1)
