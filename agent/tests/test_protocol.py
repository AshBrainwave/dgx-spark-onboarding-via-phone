import asyncio
import json
import random
import struct
import time
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

from sparkd_provision.api.handlers import Handlers
from sparkd_provision.ble_peripheral import BleProtocolBridge, _decode, _encode
from sparkd_provision.net import mock_driver
from sparkd_provision.net.capabilities import supports_concurrent_ap_sta
from sparkd_provision.net.mock_driver import MockDriver
from sparkd_provision.portal.dns import answer_a_query
from sparkd_provision.protocol.crypto import (
    b64url,
    decrypt_psk,
    derive_key,
    encrypt_psk,
    generate_keypair,
    unb64url,
)
from sparkd_provision.protocol.framing import Reassembler, fragment
from sparkd_provision.state import StateStore


async def test_mock_driver_accepts_every_documented_wifi_failure(monkeypatch) -> None:
    real_sleep = asyncio.sleep

    async def no_delay(_: float) -> None:
        await real_sleep(0)

    monkeypatch.setattr(mock_driver.asyncio, "sleep", no_delay)
    codes = (
        "WIFI_AUTH_FAILED",
        "WIFI_SSID_NOT_FOUND",
        "WIFI_WEAK_SIGNAL",
        "WIFI_DHCP_FAILED",
        "WIFI_NO_INTERNET",
        "WIFI_CAPTIVE_PORTAL",
        "WIFI_ENTERPRISE_UNSUPPORTED",
        "WIFI_BAND_MISMATCH",
        "DEVICE_LOST_AFTER_HANDOFF",
    )
    for code in codes:
        monkeypatch.setenv("SPARK_SIM_FAIL", code)
        driver = MockDriver()
        await driver.connect("Home", "password", "wpa2-psk")
        for _ in range(6):
            await real_sleep(0)
        assert (await driver.status()).err == code
    monkeypatch.delenv("SPARK_SIM_FAIL", raising=False)


def test_framing_round_trip() -> None:
    payload = b"x" * 101
    reassembler = Reassembler()
    completed = None
    for frame in fragment(payload, 42):
        completed = reassembler.add(frame) or completed
    assert completed == (42, payload)


def test_x25519_and_aes_gcm_round_trip() -> None:
    client_private, client_public = generate_keypair()
    device_private, device_public = generate_keypair()
    client_nonce = b64url(b"c" * 16)
    device_nonce = b64url(b"d" * 16)
    client_key = derive_key(client_private, device_public, client_nonce, device_nonce)
    device_key = derive_key(device_private, client_public, client_nonce, device_nonce)
    assert client_key == device_key
    assert (
        decrypt_psk(device_key, "Home", encrypt_psk(client_key, 1, "Home", "not-a-real-password"))
        == "not-a-real-password"
    )


async def test_handler_decrypts_ciphertext_without_password_on_wire() -> None:
    handlers = Handlers(MockDriver())
    client_private, client_public = generate_keypair()
    client_nonce = b64url(b"c" * 16)
    opened = await handlers.handle(
        {
            "v": 1,
            "id": "open",
            "op": "session.open",
            "sid": None,
            "body": {"client_pubkey": client_public, "nonce": client_nonce},
        }
    )
    session = opened["body"]
    key = derive_key(client_private, session["device_pubkey"], client_nonce, session["nonce"])
    password = "secret123"
    request = {
        "v": 1,
        "id": "connect",
        "op": "wifi.connect",
        "sid": session["sid"],
        "body": {
            "ssid": "Malegaonkar-5G",
            "security": "wpa2-psk",
            "psk_enc": encrypt_psk(key, 1, "Malegaonkar-5G", password),
            "hidden": False,
        },
    }
    assert password not in json.dumps(request)
    accepted = await handlers.handle(request)
    assert accepted["ok"] is True


async def test_tampered_ciphertext_returns_protocol_error() -> None:
    handlers = Handlers(MockDriver())
    _, client_public = generate_keypair()
    opened = await handlers.handle(
        {
            "v": 1,
            "id": "open",
            "op": "session.open",
            "sid": None,
            "body": {"client_pubkey": client_public, "nonce": b64url(b"n" * 16)},
        }
    )
    response = await handlers.handle(
        {
            "v": 1,
            "id": "tampered",
            "op": "wifi.connect",
            "sid": opened["body"]["sid"],
            "body": {"ssid": "Home", "security": "wpa2-psk", "psk_enc": b64url(b"x" * 40)},
        }
    )
    assert response["ok"] is False
    assert response["err"]["code"] == "INVALID_CIPHERTEXT"


def test_framing_fuzzes_sizes_order_and_drops() -> None:
    randomizer = random.Random(20260801)
    for _ in range(100):
        payload = randomizer.randbytes(randomizer.randrange(0, 1024))
        frames = fragment(payload, randomizer.randrange(1, 65535))
        shuffled = frames[:]
        randomizer.shuffle(shuffled)
        reassembler = Reassembler()
        completed = None
        for frame in shuffled:
            completed = reassembler.add(frame) or completed
        assert completed is not None
        assert completed[1] == payload
        if len(frames) > 1:
            reassembler = Reassembler()
            for frame in frames[:-1]:
                assert reassembler.add(frame) is None


def test_framing_expiry_reports_message_id() -> None:
    reassembler = Reassembler()
    reassembler.add(fragment(b"x" * 17, 77)[0])
    assert reassembler.expire(time.monotonic() + 11) == [77]


async def test_ble_bridge_decodes_handles_and_frames_response() -> None:
    sent: list[bytes] = []

    async def send(frame: bytes) -> None:
        sent.append(frame)

    bridge = BleProtocolBridge(Handlers(MockDriver()), send)
    request = {"v": 1, "id": "info", "op": "device.info", "sid": None, "body": {}}
    for frame in fragment(_encode(request), 9):
        await bridge.receive(frame)
    reassembler = Reassembler()
    response = None
    for frame in sent:
        response = reassembler.add(frame) or response
    assert response is not None
    assert _decode(response[1])["body"]["serial"] == "SIM-0001"


def test_shared_contract_fixtures_have_valid_envelopes() -> None:
    fixture_path = Path(__file__).parents[2] / "protocol" / "messages.json"
    for fixture in json.loads(fixture_path.read_text()):
        request = fixture["request"]
        assert request["v"] == 1
        assert isinstance(request["id"], str)
        assert isinstance(request["op"], str)
        assert isinstance(request["body"], dict)


def test_shared_crypto_vectors_match_protocol_ciphertext() -> None:
    vector_path = Path(__file__).parents[2] / "protocol" / "crypto-vectors.json"
    for vector in json.loads(vector_path.read_text()):
        private = X25519PrivateKey.from_private_bytes(unb64url(vector["client_private"]))
        key = derive_key(
            private, vector["device_public"], vector["client_nonce"], vector["device_nonce"]
        )
        assert (
            encrypt_psk(key, vector["counter"], vector["ssid"], vector["psk"])
            == vector["ciphertext"]
        )


def test_captive_dns_answers_any_a_query_with_ap_address() -> None:
    query = (
        struct.pack("!HHHHHH", 123, 0x0100, 1, 0, 0, 0)
        + b"\x07example\x03com\x00"
        + struct.pack("!HH", 1, 1)
    )
    response = answer_a_query(query, b"\xc0\x00\x02\x01")
    assert response is not None
    assert response[-4:] == b"\xc0\x00\x02\x01"


def test_wiphy_concurrent_ap_sta_parser_requires_two_interfaces() -> None:
    assert supports_concurrent_ap_sta("""
valid interface combinations:
 * #{ managed } <= 1, #{ AP } <= 1, total <= 2, #channels <= 1
""")
    assert not supports_concurrent_ap_sta("""
valid interface combinations:
 * #{ managed, AP } <= 1, total <= 1, #channels <= 1
""")


async def test_non_concurrent_connect_sends_handoff_before_dropping_ap(monkeypatch) -> None:
    monkeypatch.setenv("SPARK_SIM_CONCURRENT_AP_STA", "0")
    driver = MockDriver()
    handlers = Handlers(driver)
    _, public = generate_keypair()
    opened = await handlers.handle({"v": 1, "id": "open", "op": "session.open", "sid": None, "body": {"client_pubkey": public, "nonce": b64url(b"n" * 16)}})
    # Invalid cipher material is not the subject of this handoff test; use the
    # session key directly to produce an otherwise real connect envelope.
    encrypted = encrypt_psk(handlers.session_key, 1, "Home", "password")
    result = await handlers.handle({"v": 1, "id": "connect", "op": "wifi.connect", "sid": opened["body"]["sid"], "body": {"ssid": "Home", "psk_enc": encrypted}})
    assert result["body"]["handoff"]["mdns_name"] == "dgx-spark-0001.local"
    assert result["body"]["handoff"]["claim_token"]
    assert driver.ap_down_calls == 1


async def test_factory_reset_reopens_window_rotates_ap_and_restores_recovery_ap(tmp_path) -> None:
    state_path = tmp_path / "state.json"
    state = StateStore(state_path)
    old_password = state.state.ap_psk
    state.claim("old-owner")
    driver = MockDriver()
    handlers = Handlers(driver, state)

    await handlers.factory_reset()

    assert state.provisioning_open
    assert state.state.claimed is False
    assert state.state.owner_token_hash is None
    assert state.state.ap_psk != old_password
    assert driver.ap_up_calls == 1
    assert state_path.stat().st_mode & 0o777 == 0o600
