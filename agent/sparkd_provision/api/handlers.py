from __future__ import annotations

import base64
import secrets
from datetime import UTC, datetime
from typing import Any

from sparkd_provision.net.driver import NetDriver
from sparkd_provision.protocol.messages import error, network_json, response


class Handlers:
    """The one transport-independent implementation of provisioning operations."""

    def __init__(self, driver: NetDriver) -> None:
        self.driver = driver
        self.serial = "SIM-0001"
        self.sid: str | None = None
        self.owner_token: str | None = None

    async def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        message_id = request.get("id", "")
        if request.get("v") != 1 or not message_id:
            return error(message_id, "BAD_REQUEST")
        op, body = request.get("op"), request.get("body", {})
        if op == "device.info":
            return response(message_id, {"serial": self.serial, "model": "DGX Spark (sim)", "fw": "0.1.0", "state": "ADVERTISING", "capabilities": {"concurrent_ap_sta": self.driver.supports_concurrent_ap_sta}, "pubkey": "simulated-pubkey"})
        if op == "session.open":
            if self.sid and request.get("sid") != self.sid:
                return error(message_id, "SESSION_BUSY")
            self.sid = secrets.token_urlsafe(18)
            return response(message_id, {"sid": self.sid, "device_pubkey": "simulated-pubkey", "nonce": body.get("nonce", "")})
        if request.get("sid") != self.sid:
            return error(message_id, "SESSION_EXPIRED")
        if op == "wifi.scan":
            networks = await self.driver.scan(bool(body.get("force")))
            return response(message_id, {"networks": [network_json(item) for item in networks], "scanned_at": datetime.now(UTC).isoformat()})
        if op == "wifi.connect":
            if body.get("security") == "wpa2-enterprise":
                return error(message_id, "WIFI_ENTERPRISE_UNSUPPORTED")
            psk = body.get("psk_enc", "")
            await self.driver.connect(body.get("ssid", ""), psk, body.get("security", "wpa2-psk"), bool(body.get("hidden")))
            return response(message_id, {"accepted": True})
        if op == "wifi.status":
            status = await self.driver.status()
            return response(message_id, status.__dict__)
        if op == "wifi.forget":
            await self.driver.forget()
            return response(message_id, {})
        if op == "device.claim":
            self.owner_token = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")
            return response(message_id, {"owner_token": self.owner_token})
        if op == "device.rename":
            if body.get("owner_token") != self.owner_token:
                return error(message_id, "UNAUTHORIZED")
            return response(message_id, {"name": body.get("name", "DGX Spark")})
        return error(message_id, "UNKNOWN_OPERATION")
