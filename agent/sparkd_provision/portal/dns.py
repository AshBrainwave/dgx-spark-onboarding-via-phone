"""Minimal captive-portal DNS responder for SoftAP mode."""

from __future__ import annotations

import asyncio
import ipaddress
import struct


class CaptiveDnsProtocol(asyncio.DatagramProtocol):
    def __init__(self, ap_address: str) -> None:
        self.ap_address = ipaddress.IPv4Address(ap_address).packed
        self.transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport  # type: ignore[assignment]

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        response = answer_a_query(data, self.ap_address)
        if response and self.transport:
            self.transport.sendto(response, addr)


def answer_a_query(query: bytes, address: bytes) -> bytes | None:
    if len(query) < 12 or address is None:
        return None
    transaction, flags, questions, _, _, _ = struct.unpack("!HHHHHH", query[:12])
    if flags & 0x8000 or questions != 1:
        return None
    offset = 12
    while offset < len(query) and query[offset] != 0:
        offset += query[offset] + 1
    if offset + 5 > len(query):
        return None
    question = query[12 : offset + 5]
    qtype, qclass = struct.unpack("!HH", query[offset + 1 : offset + 5])
    answers = 1 if qtype == 1 and qclass == 1 else 0
    header = struct.pack("!HHHHHH", transaction, 0x8180, 1, answers, 0, 0)
    if not answers:
        return header + question
    answer = b"\xc0\x0c" + struct.pack("!HHIH", 1, 1, 60, 4) + address
    return header + question + answer


async def start_dns_responder(ap_address: str, port: int = 53) -> asyncio.DatagramTransport:
    loop = asyncio.get_running_loop()
    transport, _ = await loop.create_datagram_endpoint(
        lambda: CaptiveDnsProtocol(ap_address), local_addr=("0.0.0.0", port)
    )
    return transport
