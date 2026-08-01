"""Hardware identity discovery with an explicit override for image integration."""

from __future__ import annotations

import os
import socket
from dataclasses import dataclass
from pathlib import Path


def _read_first(paths: tuple[Path, ...]) -> str | None:
    for path in paths:
        try:
            value = path.read_text().strip("\x00\n ")
        except OSError:
            continue
        if value:
            return value
    return None


@dataclass(frozen=True)
class DeviceIdentity:
    serial: str
    model: str

    @property
    def last4(self) -> str:
        compact = "".join(character for character in self.serial if character.isalnum())
        return (compact[-4:] if compact else "0001").upper()

    @classmethod
    def simulated(cls) -> DeviceIdentity:
        return cls(serial="SIM-0001", model="DGX Spark (sim)")

    @classmethod
    def hardware(cls) -> DeviceIdentity:
        serial = os.environ.get("SPARK_SERIAL") or _read_first(
            (
                Path("/sys/class/dmi/id/product_serial"),
                Path("/sys/firmware/devicetree/base/serial-number"),
            )
        )
        serial = serial or socket.gethostname()
        model = _read_first(
            (
                Path("/sys/class/dmi/id/product_name"),
                Path("/sys/firmware/devicetree/base/model"),
            )
        )
        return cls(serial=serial, model=(model or "NVIDIA DGX Spark").replace("_", " "))
