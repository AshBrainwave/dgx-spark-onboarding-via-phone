from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

VERSION = 1

ERROR_MESSAGES = {
    "WIFI_AUTH_FAILED": "That password didn't work for this network.",
    "WIFI_SSID_NOT_FOUND": "Couldn't find that network anymore.",
    "WIFI_WEAK_SIGNAL": "Signal is too weak where your Spark is.",
    "WIFI_DHCP_FAILED": "Joined the network but couldn't get an address.",
    "WIFI_NO_INTERNET": "On your network, but no internet.",
    "WIFI_CAPTIVE_PORTAL": "This network needs a sign-in page.",
    "WIFI_ENTERPRISE_UNSUPPORTED": "Enterprise Wi-Fi isn't supported yet.",
    "WIFI_BAND_MISMATCH": "This network uses an unsupported band.",
    "SESSION_BUSY": "Someone else is setting up this Spark.",
    "SESSION_EXPIRED": "Setup window closed for safety.",
    "INVALID_CIPHERTEXT": "Credentials could not be decrypted.",
    "PUBKEY_MISMATCH": "This isn't the Spark you scanned.",
    "BLE_DISCONNECTED": "Bluetooth disconnected while setting up Spark.",
    "PORTAL_UNREACHABLE": "Phone is not connected to the Spark access point.",
    "DEVICE_LOST_AFTER_HANDOFF": "Spark could not be found after Wi-Fi changed.",
    "BAD_REQUEST": "Invalid provisioning request.",
    "UNKNOWN_OPERATION": "Unknown provisioning operation.",
}


@dataclass(frozen=True)
class Network:
    ssid: str
    bssid: str
    rssi: int
    bars: int
    security: str
    band: str
    hidden: bool = False
    saved: bool = False
    unsupported: bool = False
    reason: str | None = None
    bands: list[str] | None = None


def response(message_id: str, body: dict[str, Any]) -> dict[str, Any]:
    return {"v": VERSION, "id": message_id, "ok": True, "body": body}


def error(message_id: str, code: str, detail: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "v": VERSION,
        "id": message_id,
        "ok": False,
        "err": {"code": code, "msg": ERROR_MESSAGES.get(code, code), "detail": detail or {}},
    }


def network_json(network: Network) -> dict[str, Any]:
    return {key: value for key, value in asdict(network).items() if value is not None}
