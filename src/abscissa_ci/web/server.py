from __future__ import annotations

import argparse
import asyncio
import base64
import binascii
import json
import mimetypes
import tempfile
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from pydantic import ValidationError

from abscissa_ci.agents.tile_agent import AgentConfigurationError, extract_floor_plan_from_image
from abscissa_ci.models import TileEstimateInput
from abscissa_ci.workflows.tile_estimation import estimate_tiles


MAX_BODY_BYTES = 2_000_000
MAX_EXTRACT_BODY_BYTES = 16_000_000
IMAGE_MIME_SUFFIXES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
STATIC_PACKAGE = "abscissa_ci.web.static"


def build_estimate_response(payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    try:
        estimate_input = TileEstimateInput.model_validate(payload)
    except ValidationError as exc:
        return (
            HTTPStatus.BAD_REQUEST,
            {
                "error": "invalid_input",
                "message": "The project input does not match the tile estimate schema.",
                "details": exc.errors(),
            },
        )

    if estimate_input.input_source == "unknown":
        estimate_input.input_source = "manual"

    result = estimate_tiles(estimate_input)
    return HTTPStatus.OK, result.model_dump(mode="json")


def decode_image_payload(payload: dict[str, Any]) -> tuple[str, bytes] | tuple[None, dict[str, Any]]:
    """Returns (suffix, image_bytes) or (None, error_response)."""

    data_url = payload.get("image_data_url")
    if not isinstance(data_url, str) or not data_url.startswith("data:"):
        return None, {
            "error": "invalid_input",
            "message": "image_data_url must be a data: URL string.",
        }

    header, separator, encoded = data_url.partition(",")
    if not separator:
        return None, {
            "error": "invalid_input",
            "message": "image_data_url is missing base64 image data.",
        }

    mime_type = header.removeprefix("data:").split(";")[0].strip().lower()
    suffix = IMAGE_MIME_SUFFIXES.get(mime_type)
    if suffix is None:
        return None, {
            "error": "unsupported_image_type",
            "message": f"Unsupported image type: {mime_type or 'unknown'}. Use PNG, JPEG, or WEBP.",
        }

    try:
        image_bytes = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        return None, {
            "error": "invalid_input",
            "message": "image_data_url does not contain valid base64 data.",
        }

    return suffix, image_bytes


def build_extract_response(payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    decoded = decode_image_payload(payload)
    if decoded[0] is None:
        return HTTPStatus.BAD_REQUEST, decoded[1]
    suffix, image_bytes = decoded

    filename = payload.get("filename")
    stem = Path(filename).stem if isinstance(filename, str) and filename else "dropped_floor_plan"

    with tempfile.TemporaryDirectory() as tmp_dir:
        image_path = Path(tmp_dir) / f"floor_plan{suffix}"
        image_path.write_bytes(image_bytes)
        try:
            extraction = asyncio.run(extract_floor_plan_from_image(image_path))
        except AgentConfigurationError as exc:
            return HTTPStatus.SERVICE_UNAVAILABLE, {
                "error": "agent_unavailable",
                "message": str(exc),
            }
        except Exception as exc:
            return HTTPStatus.BAD_GATEWAY, {
                "error": "extraction_failed",
                "message": f"The extraction agent failed: {exc}",
            }

    estimate_input = {
        "project_name": extraction.project_name or stem.replace("_", " ").replace("-", " ").title(),
        "input_source": "image",
        "rectangles": [rectangle.model_dump(mode="json") for rectangle in extraction.rectangles],
        "polygons": [polygon.model_dump(mode="json") for polygon in extraction.polygons],
        "dimension_inventory": extraction.dimension_inventory,
        "validation_errors": extraction.validation_errors,
        "waste_percent": 10,
        "assumptions": [
            "Dimensions were extracted from a floor plan image by an agent.",
            "Extraction is draft-only and must be evaluated by a human reviewer.",
            *extraction.assumptions,
        ],
        "warnings": extraction.warnings,
    }
    return HTTPStatus.OK, {
        "extraction": extraction.model_dump(mode="json"),
        "estimate_input": estimate_input,
    }


class FrontendHandler(BaseHTTPRequestHandler):
    server_version = "AbscissaCIFrontend/0.1"

    def do_HEAD(self) -> None:
        parsed = urlparse(self.path)
        request_path = unquote(parsed.path)
        if request_path in {"/", "/index.html", "/app.js", "/styles.css"}:
            self.send_response(HTTPStatus.OK)
            self.end_headers()
        else:
            self.send_response(HTTPStatus.NOT_FOUND)
            self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        request_path = unquote(parsed.path)
        if request_path in {"/", "/index.html"}:
            self._send_static("index.html")
            return

        if request_path in {"/app.js", "/styles.css"}:
            self._send_static(request_path.removeprefix("/"))
            return

        self._send_json(
            HTTPStatus.NOT_FOUND,
            {"error": "not_found", "message": f"No frontend resource exists at {request_path}."},
        )

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path not in {"/api/estimate", "/api/extract"}:
            self._send_json(
                HTTPStatus.NOT_FOUND,
                {"error": "not_found", "message": f"No API route exists at {parsed.path}."},
            )
            return

        max_body = MAX_EXTRACT_BODY_BYTES if parsed.path == "/api/extract" else MAX_BODY_BYTES
        content_length = int(self.headers.get("Content-Length", "0") or "0")
        if content_length > max_body:
            self._send_json(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                {"error": "payload_too_large", "message": "The request body is too large."},
            )
            return

        try:
            body = self.rfile.read(content_length)
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"error": "invalid_json", "message": "The request body must be valid JSON."},
            )
            return

        if not isinstance(payload, dict):
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"error": "invalid_input", "message": "The request body must be a JSON object."},
            )
            return

        if parsed.path == "/api/extract":
            status, response = build_extract_response(payload)
        else:
            status, response = build_estimate_response(payload)
        self._send_json(status, response)

    def _send_static(self, filename: str) -> None:
        resource = files(STATIC_PACKAGE).joinpath(filename)
        if not resource.is_file():
            self._send_json(
                HTTPStatus.NOT_FOUND,
                {"error": "not_found", "message": f"No frontend resource exists at {filename}."},
            )
            return

        content = resource.read_bytes()
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = (json.dumps(payload, indent=2) + "\n").encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def run_server(host: str, port: int) -> None:
    httpd = ThreadingHTTPServer((host, port), FrontendHandler)
    url_host = "localhost" if host in {"", "0.0.0.0"} else host
    print(f"Serving Abscissa CI frontend at http://{url_host}:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local Abscissa CI frontend.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    run_server(args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

