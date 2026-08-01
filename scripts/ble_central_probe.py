#!/usr/bin/env python3
"""Validate the DGX Spark BLE peripheral from a macOS CoreBluetooth central."""

from __future__ import annotations

import argparse
import asyncio
import base64
import getpass
import gzip
import json
import os
import secrets
import struct
import sys
import time
from dataclasses import dataclass, field
from typing import Any

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

SERVICE_UUID = "a66a068e-b4b7-4df6-a00d-7e2c04a36f26"
CTRL_RX_UUID = "a66a068f-b4b7-4df6-a00d-7e2c04a36f26"
CTRL_TX_UUID = "a66a0690-b4b7-4df6-a00d-7e2c04a36f26"
INFO_UUID = "a66a0691-b4b7-4df6-a00d-7e2c04a36f26"
HKDF_INFO = b"dgx-spark-prov-v1"
HEADER = struct.Struct("<BBHHB")
LAST = 1
PAYLOAD_SIZE = 16


class ProbeError(RuntimeError):
    pass


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def unb64url(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def encode_message(message: dict[str, Any]) -> bytes:
    raw = json.dumps(message, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(gzip.compress(raw)).rstrip(b"=")


def decode_message(payload: bytes) -> dict[str, Any]:
    raw = gzip.decompress(
        base64.urlsafe_b64decode(payload + b"=" * (-len(payload) % 4))
    )
    message = json.loads(raw)
    if not isinstance(message, dict):
        raise ProbeError("BLE response envelope is not an object")
    return message


def fragment(payload: bytes, message_id: int) -> list[bytes]:
    chunks = [
        payload[offset : offset + PAYLOAD_SIZE]
        for offset in range(0, len(payload), PAYLOAD_SIZE)
    ]
    if not chunks:
        chunks = [b""]
    return [
        HEADER.pack(1, LAST if seq == len(chunks) - 1 else 0, message_id, seq, 0)
        + chunk
        for seq, chunk in enumerate(chunks)
    ]


@dataclass
class Reassembler:
    pending: dict[int, tuple[dict[int, bytes], int | None]] = field(
        default_factory=dict
    )

    def add(self, frame: bytes) -> tuple[int, bytes, int] | None:
        if len(frame) < HEADER.size:
            raise ProbeError(f"short BLE frame: {len(frame)} bytes")
        version, flags, message_id, seq, reserved = HEADER.unpack(frame[: HEADER.size])
        if version != 1 or reserved != 0:
            raise ProbeError(
                f"invalid BLE header: version={version}, reserved={reserved}"
            )
        if len(frame) - HEADER.size > PAYLOAD_SIZE:
            raise ProbeError(f"oversized BLE payload: {len(frame) - HEADER.size} bytes")
        parts, last = self.pending.get(message_id, ({}, None))
        parts[seq] = frame[HEADER.size :]
        if flags & LAST:
            last = seq
        self.pending[message_id] = (parts, last)
        if last is None or not all(index in parts for index in range(last + 1)):
            return None
        del self.pending[message_id]
        return message_id, b"".join(parts[index] for index in range(last + 1)), last + 1


def derive_key(
    private: X25519PrivateKey,
    peer_public: str,
    client_nonce: str,
    device_nonce: str,
) -> bytes:
    shared = private.exchange(X25519PublicKey.from_public_bytes(unb64url(peer_public)))
    salt = unb64url(client_nonce) + unb64url(device_nonce)
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=salt, info=HKDF_INFO).derive(
        shared
    )


def encrypt_psk(key: bytes, counter: int, ssid: str, psk: str) -> str:
    nonce = counter.to_bytes(12, "big")
    return b64url(nonce + AESGCM(key).encrypt(nonce, psk.encode(), ssid.encode()))


def request(
    request_id: str, op: str, sid: str | None, body: dict[str, Any]
) -> dict[str, Any]:
    return {"v": 1, "id": request_id, "op": op, "sid": sid, "body": body}


def require_ok(response: dict[str, Any], operation: str) -> dict[str, Any]:
    if response.get("ok") is not True:
        error = response.get("err", {})
        raise ProbeError(
            f"{operation} failed: {error.get('code', 'UNKNOWN')}: {error.get('msg', '')}"
        )
    body = response.get("body")
    if not isinstance(body, dict):
        raise ProbeError(f"{operation} returned a non-object body")
    return body


class BleTransport:
    def __init__(self, client: Any, rx: Any) -> None:
        self.client = client
        self.rx = rx
        self.next_message_id = 1
        self.reassembler = Reassembler()
        self.waiters: dict[int, asyncio.Future[tuple[dict[str, Any], int, int]]] = {}

    def on_notification(self, _sender: Any, data: bytearray) -> None:
        try:
            complete = self.reassembler.add(bytes(data))
            if complete is None:
                return
            message_id, payload, frame_count = complete
            waiter = self.waiters.pop(message_id, None)
            if waiter and not waiter.done():
                waiter.set_result((decode_message(payload), len(payload), frame_count))
        except (ProbeError, OSError, TypeError, ValueError) as exc:
            for waiter in self.waiters.values():
                if not waiter.done():
                    waiter.set_exception(exc)
            self.waiters.clear()

    def _allocate(self) -> tuple[int, asyncio.Future[tuple[dict[str, Any], int, int]]]:
        message_id = self.next_message_id
        self.next_message_id = self.next_message_id % 0xFFFF + 1
        waiter = asyncio.get_running_loop().create_future()
        self.waiters[message_id] = waiter
        return message_id, waiter

    async def send(
        self, message: dict[str, Any], timeout: float = 30
    ) -> tuple[dict[str, Any], int, int]:
        message_id, waiter = self._allocate()
        frames = fragment(encode_message(message), message_id)
        try:
            for frame in frames:
                await self.client.write_gatt_char(self.rx, frame, response=False)
            response, payload_bytes, response_frames = await asyncio.wait_for(
                waiter, timeout
            )
        finally:
            self.waiters.pop(message_id, None)
        if response.get("id") not in {message.get("id"), ""}:
            raise ProbeError(
                f"response id {response.get('id')!r} does not match request id {message.get('id')!r}"
            )
        return response, payload_bytes, response_frames

    async def send_incomplete(
        self, message: dict[str, Any], timeout: float = 13
    ) -> dict[str, Any]:
        message_id, waiter = self._allocate()
        frames = fragment(encode_message(message), message_id)
        if len(frames) < 2:
            raise ProbeError("timeout test request unexpectedly fit in one frame")
        try:
            for frame in frames[:-1]:
                await self.client.write_gatt_char(self.rx, frame, response=False)
            response, _, _ = await asyncio.wait_for(waiter, timeout)
            return response
        finally:
            self.waiters.pop(message_id, None)


def _load_bleak() -> tuple[Any, Any, type[Exception]]:
    try:
        from bleak import BleakClient, BleakScanner
        from bleak.exc import BleakError
    except ImportError as exc:
        raise ProbeError(
            "bleak is not installed; run `uv sync --project agent --extra probe`, then use "
            "`agent/.venv/bin/python scripts/ble_central_probe.py`"
        ) from exc
    return BleakClient, BleakScanner, BleakError


def _advertised_name(device: Any, advertisement: Any) -> str:
    return advertisement.local_name or device.name or ""


async def discover_target(timeout: float, address: str | None) -> tuple[Any, Any]:
    _, BleakScanner, BleakError = _load_bleak()
    try:
        discovered = await BleakScanner.discover(timeout=timeout, return_adv=True)
    except BleakError as exc:
        raise ProbeError(
            "CoreBluetooth scan failed. Grant Bluetooth access to this terminal under "
            f"System Settings > Privacy & Security > Bluetooth. Backend error: {exc}"
        ) from exc
    if not discovered:
        raise ProbeError(
            "CoreBluetooth found zero BLE devices. Do not debug Spark advertising yet: grant "
            "Bluetooth access to this terminal under System Settings > Privacy & Security > "
            "Bluetooth, then rerun the probe."
        )
    print(
        f"PASS macOS Bluetooth preflight: CoreBluetooth saw {len(discovered)} BLE device(s)"
    )
    values = list(discovered.values())
    if address:
        target = next(
            (item for item in values if item[0].address.lower() == address.lower()),
            None,
        )
    else:
        target = next(
            (
                item
                for item in values
                if SERVICE_UUID in {uuid.lower() for uuid in item[1].service_uuids}
                and _advertised_name(*item).startswith("DGX Spark ")
            ),
            None,
        )
        target = target or next(
            (
                item
                for item in values
                if _advertised_name(*item).startswith("DGX Spark ")
            ),
            None,
        )
    if target is None:
        raise ProbeError(
            "Mac scanning works, but no DGX Spark advertiser was found. Confirm the Spark agent "
            "is running, its provisioning window is open, and the Mac is within a few metres."
        )
    return target


def verify_advertisement(device: Any, advertisement: Any) -> None:
    uuids = {uuid.lower() for uuid in advertisement.service_uuids}
    name = _advertised_name(device, advertisement)
    if SERVICE_UUID not in uuids:
        raise ProbeError(
            f"Spark advertisement omits service UUID {SERVICE_UUID}; advertised={sorted(uuids)}"
        )
    if not name.startswith("DGX Spark ") or len(name.removeprefix("DGX Spark ")) != 4:
        raise ProbeError(
            f"invalid Spark local name {name!r}; expected 'DGX Spark <last4>'"
        )
    print(
        f"PASS C1 advertising: name={name!r}, service_uuid={SERVICE_UUID}, rssi={advertisement.rssi}"
    )


def get_characteristic(service: Any, uuid: str, required_property: str) -> Any:
    characteristic = service.get_characteristic(uuid)
    if characteristic is None:
        raise ProbeError(f"GATT characteristic {uuid} is missing")
    properties = {value.lower() for value in characteristic.properties}
    if required_property not in properties:
        raise ProbeError(
            f"GATT characteristic {uuid} lacks {required_property!r}; properties={sorted(properties)}"
        )
    return characteristic


def validate_info(raw: bytes) -> dict[str, Any]:
    try:
        info = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProbeError(f"INFO is not valid UTF-8 JSON: {exc}") from exc
    if not isinstance(info, dict) or not isinstance(info.get("serial"), str):
        raise ProbeError(f"INFO lacks a string serial: {info!r}")
    try:
        public = unb64url(info["pubkey"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ProbeError("INFO lacks a valid base64url pubkey") from exc
    if len(public) != 32:
        raise ProbeError(f"INFO X25519 public key is {len(public)} bytes, expected 32")
    return info


async def run_probe(args: argparse.Namespace) -> None:
    BleakClient, _, BleakError = _load_bleak()
    device, advertisement = await discover_target(args.scan_timeout, args.address)
    verify_advertisement(device, advertisement)
    if args.scan_only:
        return

    try:
        async with BleakClient(device, timeout=args.connect_timeout) as client:
            service = client.services.get_service(SERVICE_UUID)
            if service is None:
                raise ProbeError(f"GATT service {SERVICE_UUID} is missing")
            rx = get_characteristic(service, CTRL_RX_UUID, "write-without-response")
            tx = get_characteristic(service, CTRL_TX_UUID, "notify")
            info_characteristic = get_characteristic(service, INFO_UUID, "read")
            info = validate_info(
                bytes(await client.read_gatt_char(info_characteristic))
            )
            print(
                f"PASS C2 GATT: CTRL_RX write-without-response, CTRL_TX notify, INFO read; serial={info['serial']}"
            )

            transport = BleTransport(client, rx)
            await client.start_notify(tx, transport.on_notification)
            device_info, _, _ = await transport.send(
                request("device-info", "device.info", None, {})
            )
            device_body = require_ok(device_info, "device.info")
            if (
                device_body.get("serial") != info["serial"]
                or device_body.get("pubkey") != info["pubkey"]
            ):
                raise ProbeError(
                    "INFO snapshot does not match device.info over the framed control channel"
                )

            if not args.skip_timeout_test:
                started = time.monotonic()
                timeout_response = await transport.send_incomplete(
                    request("timeout-" + "x" * 80, "device.info", None, {})
                )
                elapsed = time.monotonic() - started
                code = timeout_response.get("err", {}).get("code")
                if code != "BLE_REASSEMBLY_TIMEOUT":
                    raise ProbeError(
                        f"incomplete fragments returned {code!r}, expected BLE_REASSEMBLY_TIMEOUT"
                    )
                print(f"PASS C3 reassembly timeout: NAK after {elapsed:.1f}s")

            client_private = X25519PrivateKey.generate()
            client_public = b64url(client_private.public_key().public_bytes_raw())
            client_nonce = b64url(secrets.token_bytes(16))
            opened, _, _ = await transport.send(
                request(
                    "session-open",
                    "session.open",
                    None,
                    {"client_pubkey": client_public, "nonce": client_nonce},
                )
            )
            session = require_ok(opened, "session.open")
            if session.get("device_pubkey") != info["pubkey"]:
                raise ProbeError("session.open device key differs from the INFO key")
            if (
                args.expected_pubkey
                and session["device_pubkey"] != args.expected_pubkey
            ):
                raise ProbeError(
                    "device public key does not match --expected-pubkey from the enrollment QR"
                )
            key = derive_key(
                client_private, session["device_pubkey"], client_nonce, session["nonce"]
            )
            sid = session.get("sid")
            if not isinstance(sid, str):
                raise ProbeError("session.open did not return a session id")

            scanned, payload_bytes, response_frames = await transport.send(
                request("wifi-scan", "wifi.scan", sid, {"force": True}),
                timeout=args.request_timeout,
            )
            scan_body = require_ok(scanned, "wifi.scan")
            networks = scan_body.get("networks")
            if not isinstance(networks, list):
                raise ProbeError("wifi.scan did not return a network list")
            print(
                f"PASS C3 real wifi.scan: {len(networks)} network(s), "
                f"{payload_bytes} encoded bytes, {response_frames} notification fragments"
            )

            if not args.skip_negative_test:
                negative_ssid = args.ssid or (
                    networks[0].get("ssid") if networks else "Truncation-Probe"
                )
                invalid, _, _ = await transport.send(
                    request(
                        "invalid-ciphertext",
                        "wifi.connect",
                        sid,
                        {
                            "ssid": negative_ssid,
                            "security": "wpa2-psk",
                            "psk_enc": b64url(os.urandom(40)),
                            "hidden": False,
                        },
                    )
                )
                code = invalid.get("err", {}).get("code")
                if code != "INVALID_CIPHERTEXT":
                    raise ProbeError(
                        f"truncated/invalid ciphertext returned {code!r}, expected INVALID_CIPHERTEXT"
                    )
                print(
                    "PASS C5 truncated ciphertext: INVALID_CIPHERTEXT, no disconnect or crash"
                )

            if not args.provision:
                print(
                    "SKIP C4 provisioning: rerun with --provision --ssid <network> to perform the real join"
                )
                return
            if not args.ssid:
                raise ProbeError("--provision requires --ssid")
            psk = (
                ""
                if args.security == "open"
                else getpass.getpass(f"Wi-Fi password for {args.ssid}: ")
            )
            encrypted = encrypt_psk(key, 1, args.ssid, psk)
            connected, _, _ = await transport.send(
                request(
                    "wifi-connect",
                    "wifi.connect",
                    sid,
                    {
                        "ssid": args.ssid,
                        "security": args.security,
                        "psk_enc": encrypted,
                        "hidden": args.hidden,
                        "band_pref": args.band_pref,
                    },
                ),
                timeout=args.request_timeout,
            )
            require_ok(connected, "wifi.connect")
            print("PASS C4 encrypted wifi.connect accepted; polling real link state")
            deadline = time.monotonic() + args.provision_timeout
            while time.monotonic() < deadline:
                status_response, _, _ = await transport.send(
                    request("wifi-status", "wifi.status", sid, {}),
                    timeout=args.request_timeout,
                )
                status = require_ok(status_response, "wifi.status")
                print(
                    f"  phase={status.get('phase')} ip={status.get('ip')} err={status.get('err')}"
                )
                if status.get("phase") == "online":
                    print(f"PASS C4 provisioning: online at {status.get('ip')}")
                    return
                if status.get("phase") == "failed":
                    raise ProbeError(f"real Wi-Fi join failed: {status.get('err')}")
                await asyncio.sleep(1)
            raise ProbeError(
                f"real Wi-Fi join did not finish within {args.provision_timeout:.0f}s"
            )
    except BleakError as exc:
        raise ProbeError(f"CoreBluetooth/GATT operation failed: {exc}") from exc


def self_test() -> None:
    for size in (0, 1, 16, 17, 255, 4096):
        payload = os.urandom(size)
        frames = fragment(payload, 42)
        assert all(len(frame) <= 23 for frame in frames)
        reassembler = Reassembler()
        complete = None
        for frame in frames:
            complete = reassembler.add(frame) or complete
        assert complete and complete[1] == payload
    envelope = request("self-test", "wifi.scan", "sid", {"force": True})
    assert decode_message(encode_message(envelope)) == envelope
    print(
        "PASS self-test: 7-byte headers, 16-byte chunks, reassembly, gzip/base64url codec"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--self-test", action="store_true", help="test framing/codec without Bluetooth"
    )
    parser.add_argument(
        "--scan-only", action="store_true", help="stop after advertising validation"
    )
    parser.add_argument("--address", help="CoreBluetooth device UUID from a prior scan")
    parser.add_argument("--scan-timeout", type=float, default=10)
    parser.add_argument("--connect-timeout", type=float, default=20)
    parser.add_argument("--request-timeout", type=float, default=45)
    parser.add_argument("--skip-timeout-test", action="store_true")
    parser.add_argument("--skip-negative-test", action="store_true")
    parser.add_argument(
        "--expected-pubkey", help="base64url device key copied from the enrollment QR"
    )
    parser.add_argument(
        "--provision", action="store_true", help="perform encrypted real-network join"
    )
    parser.add_argument("--ssid")
    parser.add_argument(
        "--security", default="wpa2-psk", choices=("open", "wpa2-psk", "wpa3-sae")
    )
    parser.add_argument("--hidden", action="store_true")
    parser.add_argument("--band-pref", choices=("2.4ghz", "5ghz", "6ghz"))
    parser.add_argument("--provision-timeout", type=float, default=90)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        self_test()
        return 0
    if sys.platform != "darwin":
        print(
            "ERROR Part C must run locally on the Mac; this is not macOS.",
            file=sys.stderr,
        )
        return 2
    try:
        asyncio.run(run_probe(args))
    except (ProbeError, asyncio.TimeoutError) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
