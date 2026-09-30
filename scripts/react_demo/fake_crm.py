"""A stand-in for the CRM service (port 8042): confirms every lead, sends nothing anywhere.

Lets the public referral form be tried without creating leads in the real Bitrix.
"""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802 - name fixed by http.server
        self.rfile.read(int(self.headers.get("content-length", 0)))
        body = json.dumps({"status": "created", "lead_id": "demo-lead"}).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args) -> None:
        return


HTTPServer(("127.0.0.1", 8042), Handler).serve_forever()
