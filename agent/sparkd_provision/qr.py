"""Enrollment QR encoding for physical and simulated Spark devices."""

from __future__ import annotations

import json
from pathlib import Path

import qrcode


def enrollment_payload(serial: str, ap_ssid: str, ap_psk: str, pubkey: str, pairing_code: str) -> str:
    return "DGXSPARK:" + json.dumps(
        {"v": 1, "serial": serial, "ap_ssid": ap_ssid, "ap_psk": ap_psk, "pubkey": pubkey, "code": pairing_code},
        separators=(",", ":"),
    )


def write_png(payload: str, output: Path) -> None:
    image = qrcode.make(payload)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)


def ascii_qr(payload: str) -> str:
    qr = qrcode.QRCode(border=1)
    qr.add_data(payload)
    qr.make(fit=True)
    return "\n".join("".join("██" if cell else "  " for cell in row) for row in qr.get_matrix())
