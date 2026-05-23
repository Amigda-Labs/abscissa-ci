import json

from abscissa_ci.agents.shell_skills import (
    AREA_SKILL_NAME,
    TILE_COUNTING_SKILL_NAME,
    RestrictedTileSkillShellExecutor,
    build_tile_skill_shell_tool,
    tile_shell_skills,
)


def test_tile_shell_skills_reference_local_skill_paths():
    skills = tile_shell_skills()

    assert [skill["name"] for skill in skills] == [AREA_SKILL_NAME, TILE_COUNTING_SKILL_NAME]
    assert all("path" in skill for skill in skills)


def test_tile_skill_shell_tool_uses_local_environment():
    tool = build_tile_skill_shell_tool()

    assert tool.environment["type"] == "local"
    assert [skill["name"] for skill in tool.environment["skills"]] == [
        AREA_SKILL_NAME,
        TILE_COUNTING_SKILL_NAME,
    ]


def test_restricted_executor_allows_tile_counting_script():
    executor = RestrictedTileSkillShellExecutor()

    output = executor.run_command(
        "python3 .agents/skills/tile-counting/scripts/count_tiles.py --area-sqm 88"
    )
    payload = json.loads(output.stdout)

    assert output.exit_code == 0
    assert payload["base_tile_count"] == 245
    assert payload["order_tile_count"] == 270


def test_restricted_executor_allows_area_script_inline_json():
    executor = RestrictedTileSkillShellExecutor()

    output = executor.run_command(
        "python3 .agents/skills/tile-area-computation/scripts/compute_area.py "
        "--json '{\"rectangles\":[{\"name\":\"Main\",\"length_m\":12,\"width_m\":5}]}'"
    )
    payload = json.loads(output.stdout)

    assert output.exit_code == 0
    assert payload["total_floor_area_sqm"] == 60


def test_restricted_executor_rejects_unrelated_shell_commands():
    executor = RestrictedTileSkillShellExecutor()

    output = executor.run_command("ls -la")

    assert output.exit_code == 2
    assert "Only python/python3 skill script commands are allowed" in output.stderr
