from __future__ import annotations

import json
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from legal_mail_setup import InfraiClient, InfraiError, configure_legal_mail, request_from_dict


class MatterMailHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        if self.path != "/configure-legal-mail":
            self._send(404, {"error": "route not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            result = configure_legal_mail(InfraiClient.from_env(), request_from_dict(payload))
            self._send(200, asdict(result))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            self._send(400, {"error": f"invalid request: {exc}"})
        except InfraiError as exc:
            status = exc.status if 400 <= exc.status < 500 else 502
            self._send(status, {"error": exc.code, "detail": exc.detail})

    def _send(self, status: int, payload: object) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8080), MatterMailHandler)
    print("Matter mail service listening on http://127.0.0.1:8080")
    server.serve_forever()
