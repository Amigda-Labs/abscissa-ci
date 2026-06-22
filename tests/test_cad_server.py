import json
from http import HTTPStatus
from http.client import HTTPConnection
from threading import Thread

from abscissa_ci.cad.server import create_server


def test_cad_server_health_and_svg_export() -> None:
    server = create_server("127.0.0.1", 0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]

    try:
        connection = HTTPConnection(host, port, timeout=5)
        connection.request("GET", "/api/health")
        response = connection.getresponse()
        health = json.loads(response.read().decode("utf-8"))
        assert response.status == HTTPStatus.OK
        assert health["ok"] is True

        project = {
            "levels": [
                {
                    "walls": [
                        {
                            "wall_id": "w1",
                            "start": {"x": 0, "y": 0},
                            "end": {"x": 3, "y": 0},
                            "wall_type": "exterior",
                        }
                    ]
                }
            ]
        }
        connection.request(
            "POST",
            "/api/export/svg",
            body=json.dumps(project),
            headers={"Content-Type": "application/json"},
        )
        response = connection.getresponse()
        body = response.read().decode("utf-8")
        assert response.status == HTTPStatus.OK
        assert response.getheader("Content-Type") == "image/svg+xml; charset=utf-8"
        assert "<svg" in body
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
