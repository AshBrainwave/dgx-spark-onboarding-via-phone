"""BLE's fixed 23-byte ATT-MTU framing, usable without a BLE radio."""

from __future__ import annotations

import struct
import time
from dataclasses import dataclass, field

HEADER = struct.Struct("<BBHHB")
PAYLOAD_SIZE = 16
LAST = 1


def fragment(payload: bytes, message_id: int) -> list[bytes]:
    if not payload:
        return [HEADER.pack(1, LAST, message_id, 0, 0)]
    chunks = [payload[i : i + PAYLOAD_SIZE] for i in range(0, len(payload), PAYLOAD_SIZE)]
    return [
        HEADER.pack(1, LAST if index == len(chunks) - 1 else 0, message_id, index, 0) + chunk
        for index, chunk in enumerate(chunks)
    ]


@dataclass
class Reassembler:
    timeout: float = 10.0
    pending: dict[int, tuple[float, dict[int, bytes], int | None]] = field(default_factory=dict)

    def add(self, frame: bytes) -> tuple[int, bytes] | None:
        if len(frame) < HEADER.size:
            raise ValueError("short frame")
        version, flags, message_id, seq, _ = HEADER.unpack(frame[: HEADER.size])
        if version != 1:
            raise ValueError("unsupported frame version")
        now = time.monotonic()
        self.pending = {key: value for key, value in self.pending.items() if now - value[0] < self.timeout}
        _, parts, last = self.pending.get(message_id, (now, {}, None))
        parts[seq] = frame[HEADER.size :]
        if flags & LAST:
            last = seq
        self.pending[message_id] = (now, parts, last)
        if last is not None and all(index in parts for index in range(last + 1)):
            del self.pending[message_id]
            return message_id, b"".join(parts[index] for index in range(last + 1))
        return None
