"""Local fixture servers validate transport behavior without touching real Orca."""

import base64
from contextlib import contextmanager
import hashlib
import importlib.util
from pathlib import Path
import socket
import socketserver
import threading
import time
import unittest


spec = importlib.util.spec_from_file_location(
    "probe_websocket", Path(__file__).resolve().parents[1] / "scripts" / "probe_websocket.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@contextmanager
def endpoint(mode):
    class Handler(socketserver.BaseRequestHandler):
        def handle(self):
            request = bytearray()
            self.request.settimeout(1)
            while b"\r\n\r\n" not in request:
                part = self.request.recv(4096)
                if not part:
                    return
                request.extend(part)
            if mode == "timeout":
                time.sleep(0.15)
                return
            if mode == "http":
                self.request.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n")
                return
            if mode == "oversized":
                self.request.sendall(b"HTTP/1.1 101 Switching Protocols\r\nX-Large: " + b"a" * 17000)
                return
            headers = dict(
                line.split(":", 1) for line in request.decode("ascii").split("\r\n")[1:] if ":" in line
            )
            key = headers["Sec-WebSocket-Key"].strip()
            accept = base64.b64encode(hashlib.sha1((key + module.GUID).encode("ascii")).digest()).decode("ascii")
            if mode == "invalid_accept":
                accept = "incorrect"
            response = (
                "HTTP/1.1 101 Switching Protocols\r\n"
                "uPgRaDe: WebSocket\r\nConnection: keep-alive, Upgrade\r\n"
                f"Sec-WebSocket-Accept: {accept}\r\n\r\n"
            ).encode("ascii")
            if mode == "fragmented":
                self.request.sendall(response[:11])
                time.sleep(0.01)
                self.request.sendall(response[11:])
            else:
                self.request.sendall(response)

    with socketserver.ThreadingTCPServer(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        thread.start()
        try:
            yield server.server_address[1]
        finally:
            server.shutdown()
            thread.join(timeout=1)


class ProbeTests(unittest.TestCase):
    def test_success_never_claims_orca_authentication(self):
        with endpoint("valid") as port:
            result = module.probe("127.0.0.1", port)
        self.assertTrue(result["tcp_connected"])
        self.assertTrue(result["websocket_upgrade"])
        self.assertFalse(result["authenticated"])

    def test_fragmented_headers(self):
        with endpoint("fragmented") as port:
            self.assertTrue(module.probe("127.0.0.1", port)["websocket_upgrade"])

    def test_101_with_wrong_accept_is_failure(self):
        with endpoint("invalid_accept") as port:
            result = module.probe("127.0.0.1", port)
        self.assertEqual(result["http_status"], 101)
        self.assertFalse(result["websocket_upgrade"])

    def test_http_service_is_not_websocket(self):
        with endpoint("http") as port:
            result = module.probe("127.0.0.1", port)
        self.assertEqual(result["http_status"], 200)
        self.assertFalse(result["websocket_upgrade"])

    def test_read_timeout(self):
        with endpoint("timeout") as port:
            result = module.probe("127.0.0.1", port, timeout=0.03)
        self.assertFalse(result["websocket_upgrade"])
        self.assertIn("timeout", result["error"].lower())

    def test_header_size_limit(self):
        with endpoint("oversized") as port:
            result = module.probe("127.0.0.1", port)
        self.assertFalse(result["websocket_upgrade"])
        self.assertIn("size limit", result["error"])

    def test_refused_tcp(self):
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            # Bound without listen, so the port is reserved but rejects TCP.
            result = module.probe("127.0.0.1", reservation.getsockname()[1], timeout=0.2)
        self.assertFalse(result["tcp_connected"])
        self.assertFalse(result["websocket_upgrade"])

    def test_rejects_url_and_credentials(self):
        for host in ("ws://example.test", "user:secret@example.test", "example.test\r\nInjected: true"):
            with self.subTest(host=host), self.assertRaises(ValueError):
                module.probe(host)


if __name__ == "__main__":
    unittest.main()
