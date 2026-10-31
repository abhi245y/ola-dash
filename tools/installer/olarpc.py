"""Minimal client vendored from ola-s1-rea/scripts/ola.py; no CLI.

MIT License
Copyright (c) 2026 Ola S1 REA contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

Adaptations: lazy grpc import, Linux interface scopes, IPv6 validation,
connection errors without remote output. Only payload/target/connect/call
helpers needed by the read-only installer are retained.
"""
from __future__ import annotations

import ipaddress

PORT = 50005
MAX_MSG = 64 << 20


def _vi(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | 0x80 if n else b)
        if not n:
            return bytes(out)


def _cmd_payload(text: str) -> bytes:
    raw = text.encode()
    return _vi((1 << 3) | 2) + _vi(len(raw)) + raw


def _read_varint(buf: bytes, i: int):
    value = shift = 0
    while True:
        b = buf[i]
        i += 1
        value |= (b & 0x7F) << shift
        if not b & 0x80:
            return value, i
        shift += 7


def _decode_response(buf: bytes):
    fields: dict[int, object] = {}
    i = 0
    while i < len(buf):
        key, i = _read_varint(buf, i)
        field, wire = key >> 3, key & 7
        if wire == 0:
            fields[field], i = _read_varint(buf, i)
        elif wire == 2:
            length, i = _read_varint(buf, i)
            fields[field] = buf[i:i + length].decode("utf-8", "replace")
            i += length
        else:
            break
    return fields.get(1, 0), fields.get(2, "")


def build_target(host: str, port: int = PORT, scope: str | int | None = None) -> str:
    h = host.strip()
    if h.lower().startswith("ipv6:"):
        h = h[5:].strip()
    if h.startswith("[") and h.endswith("]"):
        h = h[1:-1]
    address, separator, zone = h.partition("%")
    ip = ipaddress.IPv6Address(address)
    if separator and (not zone or "%" in zone):
        raise ValueError("Invalid IPv6 scope")
    if separator and scope is not None and zone != str(scope):
        raise ValueError("Conflicting IPv6 scopes")
    if not separator and scope is not None:
        zone = str(scope)
    if zone and not all(c.isalnum() or c in "_.-" for c in zone):
        raise ValueError("Invalid IPv6 scope")
    if ip.is_link_local and not zone:
        raise ValueError("Link-local IPv6 needs %iface or --scope")
    h = str(ip) + (f"%{zone}" if zone else "")
    return f"ipv6:[{h}]:{port}"


def connect(target: str, wait: float):
    try:
        import grpc
    except ImportError:
        raise RuntimeError("Missing grpcio. Run: pip install grpcio") from None

    channel = grpc.insecure_channel(
        target,
        options=[("grpc.max_receive_message_length", MAX_MSG),
                 ("grpc.max_send_message_length", MAX_MSG)])
    try:
        grpc.channel_ready_future(channel).result(timeout=wait)
    except Exception:
        channel.close()
        raise RuntimeError("Diagnostics service did not connect") from None
    return channel


def call(channel, command: str, timeout: float):
    fn = channel.unary_unary(
        "/wifican.WifiCanRpc/ExecuteADBCommand",
        request_serializer=lambda b: b,
        response_deserializer=lambda b: b)
    raw = fn(_cmd_payload(command), timeout=timeout)
    return _decode_response(raw)
