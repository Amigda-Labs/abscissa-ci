from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from pydantic import ValidationError

from abscissa_ci.agents.cad_agent import (
    CadAgentConfigurationError,
    configured_model as configured_cad_agent_model,
    is_configured as is_cad_agent_configured,
    respond_to_cad_chat,
)
from abscissa_ci.cad.export import export_project_svg
from abscissa_ci.cad.models import CadProject, create_default_project


STATIC_DIR = Path(__file__).resolve().parent / "static"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


class CadRequestHandler(SimpleHTTPRequestHandler):
    server_version = "AbscissaCadHTTP/0.1"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def do_GET(self) -> None:
        if self.path == "/api/health":
            self._send_json({"ok": True, "app": "abscissa-cad", "schema_version": "abscissa-cad-v1"})
            return
        if self.path == "/api/default-project":
            project = create_default_project()
            self._send_json(project.model_dump(mode="json"))
            return
        if self.path == "/api/agent/status":
            self._send_json(
                {
                    "ok": True,
                    "configured": is_cad_agent_configured(),
                    "model": configured_cad_agent_model(),
                }
            )
            return
        if self.path == "/favicon.ico":
            self.send_response(HTTPStatus.NO_CONTENT)
            self.end_headers()
            return
        super().do_GET()

    def do_POST(self) -> None:
        if self.path == "/api/validate-project":
            self._handle_validate_project()
            return
        if self.path == "/api/export/svg":
            self._handle_export_svg()
            return
        if self.path == "/api/agent/chat":
            self._handle_agent_chat()
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Unknown API endpoint")

    def translate_path(self, path: str) -> str:
        clean_path = unquote(path.split("?", 1)[0].split("#", 1)[0])
        if clean_path == "/":
            clean_path = "/index.html"
        return str(STATIC_DIR / clean_path.lstrip("/"))

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[abscissa-cad] {self.address_string()} - {format % args}")

    def _handle_validate_project(self) -> None:
        try:
            project = CadProject.model_validate(self._read_json_body())
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        self._send_json({"ok": True, "project": project.model_dump(mode="json")})

    def _handle_export_svg(self) -> None:
        try:
            project = CadProject.model_validate(self._read_json_body())
            svg = export_project_svg(project)
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        encoded = svg.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _handle_agent_chat(self) -> None:
        try:
            payload = self._read_json_body()
            message = str(payload.get("message", "")).strip()
            if not message:
                raise ValueError("message is required")
            reply = respond_to_cad_chat(message)
        except CadAgentConfigurationError as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.SERVICE_UNAVAILABLE)
            return
        except (json.JSONDecodeError, ValueError) as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        except Exception as exc:  # pragma: no cover - depends on external provider
            self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_GATEWAY)
            return
        self._send_json({"ok": True, "reply": reply, "model": configured_cad_agent_model()})

    def _read_json_body(self) -> Any:
        length = int(self.headers.get("Content-Length", "0"))
        payload = self.rfile.read(length).decode("utf-8")
        return json.loads(payload)

    def _send_json(self, payload: Any, *, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def create_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), CadRequestHandler)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="abscissa-cad")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)

    server = create_server(args.host, args.port)
    host, port = server.server_address[:2]
    print(f"Abscissa CAD running at http://{host}:{port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Abscissa CAD.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
