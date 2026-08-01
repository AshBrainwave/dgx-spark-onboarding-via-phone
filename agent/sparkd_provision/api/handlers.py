from __future__ import annotations

import base64
import secrets
from datetime import UTC, datetime
from typing import Any

from sparkd_provision.net.driver import NetDriver
from sparkd_provision.protocol.crypto import b64url, decrypt_psk, derive_key, generate_keypair
from sparkd_provision.protocol.messages import error, network_json, response


class Handlers:
    """The one transport-independent implementation of provisioning operations."""

    def __init__(self, driver: NetDriver) -> None:
        self.driver = driver
        self.serial = "SIM-0001"
        self.device_private, self.device_public = generate_keypair()
        self.sid: str | None = None
        self.session_key: bytes | None = None
        self.owner_token: str | None = None

    async def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        message_id = request.get("id", "")
        if request.get("v") != 1 or not message_id:
            return error(message_id, "BAD_REQUEST")
        op, body = request.get("op"), request.get("body", {})
        if not isinstance(body, dict):
            return error(message_id, "BAD_REQUEST")
        if op == "device.info":
            return response(message_id, {"serial": self.serial, "model": "DGX Spark (sim)", "fw": "0.1.0", "state": "ADVERTISING", "capabilities": {"concurrent_ap_sta": self.driver.supports_concurrent_ap_sta}, "pubkey": self.device_public})
        if op == "session.open":
            if self.sid and request.get("sid") != self.sid:
                return error(message_id, "SESSION_BUSY")
            client_public = body.get("client_pubkey")
            client_nonce = body.get("nonce")
            if not isinstance(client_public, str) or not isinstance(client_nonce, str):
                return error(message_id, "BAD_REQUEST")
            device_nonce = b64url(secrets.token_bytes(16))
            try:
                self.session_key = derive_key(self.device_private, client_public, client_nonce, device_nonce)
            except ValueError:
                return error(message_id, "BAD_REQUEST")
            self.sid = secrets.token_urlsafe(18)
            return response(message_id, {"sid": self.sid, "device_pubkey": self.device_public, "nonce": device_nonce})
        if op not in {"wifi.scan", "wifi.connect", "wifi.status", "wifi.forget", "device.claim", "device.rename", "device.factory_reset"}:
            return error(message_id, "UNKNOWN_OPERATION")
        if request.get("sid") != self.sid:
            return error(message_id, "SESSION_EXPIRED")
        if op == "wifi.scan":
            networks = await self.driver.scan(bool(body.get("force")))
            return response(message_id, {"networks": [network_json(item) for item in networks], "scanned_at": datetime.now(UTC).isoformat()})
        if op == "wifi.connect":
            if body.get("security") == "wpa2-enterprise":
                return error(message_id, "WIFI_ENTERPRISE_UNSUPPORTED")
            ciphertext = body.get("psk_enc")
            ssid = body.get("ssid")
            if not self.session_key or not isinstance(ciphertext, str) or not isinstance(ssid, str):
                return error(message_id, "BAD_REQUEST")
            try:
                psk = decrypt_psk(self.session_key, ssid, ciphertext)
            except (ValueError, TypeError):
                return error(message_id, "INVALID_CIPHERTEXT")
            await self.driver.connect(ssid, psk, body.get("security", "wpa2-psk"), bool(body.get("hidden")))
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

    async def provisioning_online(self) -> bool:
        return (await self.driver.status()).phase == "online"
