from __future__ import annotations

import asyncio
import base64
import secrets
from datetime import UTC, datetime
from typing import Any

from cryptography.exceptions import InvalidTag

from sparkd_provision.net.driver import NetDriver
from sparkd_provision.net.mdns import MdnsPublisher
from sparkd_provision.protocol.crypto import b64url, decrypt_psk, derive_key, generate_keypair
from sparkd_provision.protocol.messages import error, network_json, response
from sparkd_provision.state import StateStore


class Handlers:
    """The one transport-independent implementation of provisioning operations."""

    def __init__(
        self, driver: NetDriver, state: StateStore | None = None, mdns: MdnsPublisher | None = None
    ) -> None:
        self.driver = driver
        self.state = state or StateStore()
        self.mdns = mdns
        self.serial = "SIM-0001"
        self.device_private, self.device_public = generate_keypair()
        self.sid: str | None = None
        self.session_key: bytes | None = None
        self.owner_token: str | None = None
        self.session_opened_at: datetime | None = None
        self.connect_attempts = 0
        self.next_connect_at: datetime | None = None
        self._handoff_task: asyncio.Task[None] | None = None

    async def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        message_id = request.get("id", "")
        if request.get("v") != 1 or not message_id:
            return error(message_id, "BAD_REQUEST")
        op, body = request.get("op"), request.get("body", {})
        if not isinstance(body, dict):
            return error(message_id, "BAD_REQUEST")
        if op == "device.info":
            return response(message_id, {"serial": self.serial, "model": "DGX Spark (sim)", "fw": "0.1.0", "state": "PROVISIONED" if self.state.state.claimed else "ADVERTISING", "capabilities": {"concurrent_ap_sta": self.driver.supports_concurrent_ap_sta}, "pubkey": self.device_public})
        if op == "session.open":
            injected = getattr(self.driver, "failure", "")
            if injected == "session_busy":
                return error(message_id, "SESSION_BUSY")
            if injected == "session_expired":
                return error(message_id, "SESSION_EXPIRED")
            if injected == "pubkey_mismatch":
                return error(message_id, "PUBKEY_MISMATCH")
            if injected == "ble_disconnected":
                return error(message_id, "BLE_DISCONNECTED")
            if injected == "portal_unreachable":
                return error(message_id, "PORTAL_UNREACHABLE")
            if not self.state.provisioning_open:
                return error(message_id, "SESSION_EXPIRED")
            if self.sid and self.session_opened_at and (datetime.now(UTC) - self.session_opened_at).total_seconds() >= 90:
                self._release_session()
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
            self.session_opened_at = datetime.now(UTC)
            self.connect_attempts = 0
            self.next_connect_at = None
            return response(message_id, {"sid": self.sid, "device_pubkey": self.device_public, "nonce": device_nonce})
        if op not in {"wifi.scan", "wifi.connect", "wifi.status", "wifi.forget", "device.claim", "device.rename", "device.factory_reset"}:
            return error(message_id, "UNKNOWN_OPERATION")
        if request.get("sid") != self.sid:
            return error(message_id, "SESSION_EXPIRED")
        if op == "wifi.scan":
            networks = await self.driver.scan(bool(body.get("force")))
            return response(message_id, {"networks": [network_json(item) for item in networks], "scanned_at": datetime.now(UTC).isoformat()})
        if op == "wifi.connect":
            if getattr(self.driver, "failure", "") == "wifi_enterprise_unsupported":
                return error(message_id, "WIFI_ENTERPRISE_UNSUPPORTED")
            if body.get("security") == "wpa2-enterprise":
                return error(message_id, "WIFI_ENTERPRISE_UNSUPPORTED")
            ciphertext = body.get("psk_enc")
            ssid = body.get("ssid")
            if not self.session_key or not isinstance(ciphertext, str) or not isinstance(ssid, str):
                return error(message_id, "BAD_REQUEST")
            now = datetime.now(UTC)
            if self.connect_attempts >= 5:
                return error(message_id, "RATE_LIMITED")
            if self.next_connect_at and now < self.next_connect_at:
                return error(message_id, "RETRY_BACKOFF")
            try:
                psk = decrypt_psk(self.session_key, ssid, ciphertext)
            except (InvalidTag, ValueError, TypeError):
                return error(message_id, "INVALID_CIPHERTEXT")
            self.connect_attempts += 1
            # 1, 2, 4, 8, 16 seconds following attempts; the first stays immediate.
            from datetime import timedelta
            self.next_connect_at = now + timedelta(seconds=max(0, 2 ** (self.connect_attempts - 1) - 1))
            handoff: dict[str, str] = {}
            if not self.driver.supports_concurrent_ap_sta:
                # This is deliberately delivered while the AP still exists.  The
                # token is an opaque correlation value, not an owner credential.
                handoff = {
                    "mdns_name": "dgx-spark-0001.local",
                    "expected_hostname": "dgx-spark-0001",
                    "claim_token": secrets.token_urlsafe(24),
                }
                await self.driver.softap_down()
            await self.driver.connect(ssid, psk, body.get("security", "wpa2-psk"), bool(body.get("hidden")))
            if handoff:
                self._handoff_task = asyncio.create_task(self._recover_ap_after_failed_handoff())
            return response(message_id, {"accepted": True, "handoff": handoff or None})
        if op == "wifi.status":
            status = await self.driver.status()
            if status.phase == "online" and self.mdns:
                # Avahi owns conflict handling; a failed publisher must not make a
                # successfully provisioned device appear to have failed Wi-Fi.
                try:
                    await self.mdns.publish("DGX Spark", "dgx-spark-0001.local")
                except RuntimeError:
                    pass
            if status.phase == "failed":
                self._release_session()
            return response(message_id, status.__dict__)
        if op == "wifi.forget":
            await self.driver.forget()
            return response(message_id, {})
        if op == "device.claim":
            self.owner_token = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")
            self.state.claim(self.owner_token)
            return response(message_id, {"owner_token": self.owner_token})
        if op == "device.rename":
            if not self.state.token_matches(body.get("owner_token")):
                return error(message_id, "UNAUTHORIZED")
            self.state.state.name = str(body.get("name", "DGX Spark"))
            self.state.save()
            return response(message_id, {"name": self.state.state.name})
        if op == "device.factory_reset":
            self._release_session()
            self.state.reset()
            await self.driver.forget()
            return response(message_id, {})
        return error(message_id, "UNKNOWN_OPERATION")

    async def provisioning_online(self) -> bool:
        return (await self.driver.status()).phase == "online"

    def _release_session(self) -> None:
        self.sid = None
        self.session_key = None
        self.session_opened_at = None
        self.connect_attempts = 0
        self.next_connect_at = None

    async def _recover_ap_after_failed_handoff(self) -> None:
        """Restore the only recovery path if a non-concurrent join fails.

        This runs independently of a phone polling a now-disconnected portal.
        NetworkManager normally reaches a terminal failure quickly; the 20-second
        deadline is the UX contract and a later failure is still recovered.
        """
        for _ in range(20):
            await asyncio.sleep(1)
            status = await self.driver.status()
            if status.phase == "online":
                return
            if status.phase == "failed":
                await self.driver.softap_up(self.state.state.ap_ssid, self.state.state.ap_psk)
                return
