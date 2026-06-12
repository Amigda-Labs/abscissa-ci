import base64
from http import HTTPStatus

from abscissa_ci.web.server import build_estimate_response, build_extract_response


# 1x1 transparent PNG
TINY_PNG_B64 = base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000d4944415478da63fcffffff7f0005fe02fea736a8590000000049454e44ae426082"
    )
).decode("ascii")


def test_frontend_estimate_response_returns_area_solution_and_tile_counts():
    status, payload = build_estimate_response(
        {
            "project_name": "Frontend L Shape",
            "input_source": "manual",
            "polygons": [
                {
                    "name": "L Shape Footprint",
                    "operation": "add",
                    "points": [
                        {"x_m": 0, "y_m": 0},
                        {"x_m": 12, "y_m": 0},
                        {"x_m": 12, "y_m": 5},
                        {"x_m": 7, "y_m": 5},
                        {"x_m": 7, "y_m": 9},
                        {"x_m": 0, "y_m": 9},
                    ],
                    "edge_labels": [
                        {"edge_index": 0, "length_m": 12, "source_text": "12.00 m"},
                        {"edge_index": 5, "length_m": 9, "source_text": "9.00 m"},
                    ],
                }
            ],
            "waste_percent": 10,
        }
    )

    assert status == HTTPStatus.OK
    assert payload["can_compute"] is True
    assert payload["total_floor_area_sqm"] == 88
    assert payload["base_tile_count"] == 245
    assert payload["order_tile_count"] == 270
    assert payload["polygons"][0]["calculation"] == "add shoelace(6 vertices) = 88 sqm"


def test_frontend_estimate_response_reports_schema_errors():
    status, payload = build_estimate_response(
        {
            "project_name": "Bad Input",
            "rectangles": [
                {"name": "Invalid", "length_m": 0, "width_m": 4},
            ],
        }
    )

    assert status == HTTPStatus.BAD_REQUEST
    assert payload["error"] == "invalid_input"
    assert payload["details"]


def test_extract_rejects_missing_data_url():
    status, payload = build_extract_response({"filename": "plan.png"})

    assert status == HTTPStatus.BAD_REQUEST
    assert payload["error"] == "invalid_input"


def test_extract_rejects_unsupported_image_type():
    status, payload = build_extract_response(
        {"image_data_url": f"data:image/gif;base64,{TINY_PNG_B64}"}
    )

    assert status == HTTPStatus.BAD_REQUEST
    assert payload["error"] == "unsupported_image_type"


def test_extract_rejects_invalid_base64():
    status, payload = build_extract_response(
        {"image_data_url": "data:image/png;base64,not-valid-base64!!!"}
    )

    assert status == HTTPStatus.BAD_REQUEST
    assert payload["error"] == "invalid_input"


def test_extract_reports_agent_unavailable_without_api_key(monkeypatch):
    monkeypatch.setenv("ABSCISSA_DISABLE_DOTENV", "1")
    monkeypatch.delenv("ABSCISSA_TILE_ENGINEER_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    status, payload = build_extract_response(
        {"filename": "plan.png", "image_data_url": f"data:image/png;base64,{TINY_PNG_B64}"}
    )

    assert status == HTTPStatus.SERVICE_UNAVAILABLE
    assert payload["error"] == "agent_unavailable"


def test_extract_builds_estimate_input_from_extraction(monkeypatch):
    from abscissa_ci import web
    from abscissa_ci.models import FloorPlanExtraction, PolygonDraft, PolygonPoint

    async def fake_extract(image_path, model=None, use_shell_skills=False):
        return FloorPlanExtraction(
            polygons=[
                PolygonDraft(
                    name="Main Floor",
                    points=[
                        PolygonPoint(x_m=0, y_m=0),
                        PolygonPoint(x_m=10, y_m=0),
                        PolygonPoint(x_m=10, y_m=8),
                        PolygonPoint(x_m=0, y_m=8),
                    ],
                )
            ],
            assumptions=["Test assumption."],
        )

    monkeypatch.setattr(web.server, "extract_floor_plan_from_image", fake_extract)

    status, payload = build_extract_response(
        {"filename": "office_plan.png", "image_data_url": f"data:image/png;base64,{TINY_PNG_B64}"}
    )

    assert status == HTTPStatus.OK
    estimate_input = payload["estimate_input"]
    assert estimate_input["project_name"] == "Office Plan"
    assert estimate_input["input_source"] == "image"
    assert estimate_input["polygons"][0]["name"] == "Main Floor"
    assert "Test assumption." in estimate_input["assumptions"]
