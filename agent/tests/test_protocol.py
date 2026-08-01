import json
import random
import struct
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

from sparkd_provision.api.handlers import Handlers
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
    assert decrypt_psk(device_key, "Home", encrypt_psk(client_key, 1, "Home", "not-a-real-password")) == "not-a-real-password"


async def test_handler_decrypts_ciphertext_without_password_on_wire() -> None:
    handlers = Handlers(MockDriver())
    client_private, client_public = generate_keypair()
    client_nonce = b64url(b"c" * 16)
    opened = await handlers.handle({"v": 1, "id": "open", "op": "session.open", "sid": None, "body": {"client_pubkey": client_public, "nonce": client_nonce}})
    session = opened["body"]
    key = derive_key(client_private, session["device_pubkey"], client_nonce, session["nonce"])
    password = "secret123"
    request = {"v": 1, "id": "connect", "op": "wifi.connect", "sid": session["sid"], "body": {"ssid": "Malegaonkar-5G", "security": "wpa2-psk", "psk_enc": encrypt_psk(key, 1, "Malegaonkar-5G", password), "hidden": False}}
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
        key = derive_key(private, vector["device_public"], vector["client_nonce"], vector["device_nonce"])
        assert encrypt_psk(key, vector["counter"], vector["ssid"], vector["psk"]) == vector["ciphertext"]


def test_captive_dns_answers_any_a_query_with_ap_address() -> None:
    query = struct.pack("!HHHHHH", 123, 0x0100, 1, 0, 0, 0) + b"\x07example\x03com\x00" + struct.pack("!HH", 1, 1)
    response = answer_a_query(query, b"\xc0\x00\x02\x01")
    assert response is not None
    assert response[-4:] == b"\xc0\x00\x02\x01"
