#!/usr/bin/env python3
"""Probe TCP and RFC 6455 upgrade only; never pair or authenticate to Orca."""

import argparse
import base64
import hashlib
import json
import math
import secrets
import socket
import time


GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
MAX_HEADER_BYTES = 16384


def probe(host, port=6768, timeout=8.0):
    """Return a bounded, credential-free transport observation."""
    if not host or any(char.isspace() for char in host) or any(
        char in host for char in "/@?#\\"
    ):
        raise ValueError("host must be a bare IP address or hostname")
    if not 1 <= port <= 65535:
        raise ValueError("port must be between 1 and 65535")
    if not math.isfinite(timeout) or not 0 < timeout <= 60:
        raise ValueError("timeout must be greater than 0 and at most 60 seconds")

    started = time.monotonic()
    deadline = started + timeout
    result = {
        "host": host,
        "port": port,
        "tcp_connected": False,
        "http_status": None,
        "websocket_upgrade": False,
        "authenticated": False,
        "scope": "transport_only_no_orca_authentication",
    }
    key = base64.b64encode(secrets.token_bytes(16)).decode("ascii")
    authority = f"[{host}]" if ":" in host and not host.startswith("[") else host
    request = (
        f"GET / HTTP/1.1\r\nHost: {authority}:{port}\r\n"
        "Upgrade: websocket\r\nConnection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
    ).encode("ascii")
    try:
        with socket.create_connection((host, port), timeout=timeout) as connection:
            result["tcp_connected"] = True
            connection.settimeout(max(0.001, deadline - time.monotonic()))
            connection.sendall(request)
            received = bytearray()
            while b"\r\n\r\n" not in received:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("response timeout")
                connection.settimeout(remaining)
                chunk = connection.recv(min(4096, MAX_HEADER_BYTES - len(received)))
                if not chunk:
                    raise ValueError("connection closed before complete HTTP headers")
                received.extend(chunk)
                if b"\r\n\r\n" not in received and len(received) >= MAX_HEADER_BYTES:
                    raise ValueError("HTTP headers exceed size limit")
            lines = bytes(received).split(b"\r\n\r\n", 1)[0].decode("iso-8859-1").split("\r\n")
            status = lines[0].split()
            if len(status) < 2 or not status[0].startswith("HTTP/"):
                raise ValueError("invalid HTTP status line")
            result["http_status"] = int(status[1])
            headers = {}
            for line in lines[1:]:
                name, separator, value = line.partition(":")
                if not separator:
                    raise ValueError("invalid HTTP header")
                name = name.strip().lower()
                headers[name] = headers.get(name, "") + ("," if name in headers else "") + value.strip()
            expected = base64.b64encode(hashlib.sha1((key + GUID).encode("ascii")).digest()).decode("ascii")
            connection_tokens = {token.strip().lower() for token in headers.get("connection", "").split(",")}
            result["websocket_upgrade"] = (
                result["http_status"] == 101
                and headers.get("upgrade", "").lower() == "websocket"
                and "upgrade" in connection_tokens
                and headers.get("sec-websocket-accept") == expected
            )
            if not result["websocket_upgrade"]:
                result["error"] = "response did not contain a valid WebSocket upgrade"
    except (OSError, ValueError) as error:
        result["error"] = f"{type(error).__name__}: {error}"
    result["elapsed_ms"] = round((time.monotonic() - started) * 1000, 1)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, help="Bare Tailscale IP or hostname; no URL or credentials")
    parser.add_argument("--port", type=int, default=6768)
    parser.add_argument("--timeout", type=float, default=8.0, help="Socket operation budget, up to 60 seconds; OS DNS may take longer")
    args = parser.parse_args()
    try:
        result = probe(args.host, args.port, args.timeout)
    except (ValueError, UnicodeError) as error:
        parser.error(str(error))
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["websocket_upgrade"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
