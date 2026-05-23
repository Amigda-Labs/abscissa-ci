from __future__ import annotations

import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

from agents import ShellActionRequest, ShellCallOutcome, ShellCommandOutput, ShellResult, ShellTool


ROOT = Path(__file__).resolve().parents[3]
SKILLS_ROOT = ROOT / ".agents" / "skills"
AREA_SKILL_NAME = "tile-area-computation"
TILE_COUNTING_SKILL_NAME = "tile-counting"


def tile_area_skill() -> dict[str, str]:
    return {
        "name": AREA_SKILL_NAME,
        "description": (
            "Compute floor area from add/subtract rectangular floor-plan parts, "
            "including decomposed L/T/plus shapes and voids."
        ),
        "path": str(SKILLS_ROOT / AREA_SKILL_NAME),
    }


def tile_counting_skill() -> dict[str, str]:
    return {
        "name": TILE_COUNTING_SKILL_NAME,
        "description": "Count 600mm x 600mm tiles from total floor area and waste percentage.",
        "path": str(SKILLS_ROOT / TILE_COUNTING_SKILL_NAME),
    }


def tile_shell_skills() -> list[dict[str, str]]:
    return [tile_area_skill(), tile_counting_skill()]


class RestrictedTileSkillShellExecutor:
    """Execute only the bundled tile skill scripts for local ShellTool calls."""

    def __init__(self, root: Path = ROOT) -> None:
        self.root = root
        self.allowed_scripts = {
            (SKILLS_ROOT / AREA_SKILL_NAME / "scripts" / "compute_area.py").resolve(),
            (SKILLS_ROOT / TILE_COUNTING_SKILL_NAME / "scripts" / "count_tiles.py").resolve(),
        }

    def _normalize_python(self, executable: str) -> bool:
        return executable in {"python", "python3", Path(sys.executable).name, sys.executable}

    def _resolve_script(self, script: str) -> Path:
        path = Path(script)
        if not path.is_absolute():
            path = self.root / path
        return path.resolve()

    def validate_command(self, command: str) -> list[str]:
        args = shlex.split(command)
        if len(args) < 2:
            raise ValueError("Command must call python with a bundled skill script.")
        if not self._normalize_python(args[0]):
            raise ValueError("Only python/python3 skill script commands are allowed.")

        script_path = self._resolve_script(args[1])
        if script_path not in self.allowed_scripts:
            raise ValueError(f"Script is not an allowed tile skill script: {args[1]}")

        args[0] = sys.executable
        args[1] = str(script_path)
        return args

    def run_command(self, command: str, timeout_ms: int | None = None) -> ShellCommandOutput:
        try:
            args = self.validate_command(command)
            completed = subprocess.run(
                args,
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=(timeout_ms / 1000) if timeout_ms else 30,
            )
            return ShellCommandOutput(
                stdout=completed.stdout,
                stderr=completed.stderr,
                outcome=ShellCallOutcome(type="exit", exit_code=completed.returncode),
                command=command,
            )
        except subprocess.TimeoutExpired as exc:
            return ShellCommandOutput(
                stdout=exc.stdout or "",
                stderr=exc.stderr or "Command timed out.",
                outcome=ShellCallOutcome(type="timeout", exit_code=None),
                command=command,
            )
        except Exception as exc:
            return ShellCommandOutput(
                stdout="",
                stderr=str(exc),
                outcome=ShellCallOutcome(type="exit", exit_code=2),
                command=command,
            )

    async def __call__(self, request: Any) -> ShellResult:
        action: ShellActionRequest = request.data.action
        outputs = [
            self.run_command(command, timeout_ms=action.timeout_ms)
            for command in action.commands
        ]
        return ShellResult(output=outputs, max_output_length=action.max_output_length)


def build_tile_skill_shell_tool() -> ShellTool:
    return ShellTool(
        environment={
            "type": "local",
            "skills": tile_shell_skills(),
        },
        executor=RestrictedTileSkillShellExecutor(),
    )
