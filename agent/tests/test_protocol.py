from sparkd_provision.protocol.crypto import decrypt_psk, derive_key, encrypt_psk, generate_keypair
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
    client_key = derive_key(client_private, device_public, "client", "device")
    device_key = derive_key(device_private, client_public, "client", "device")
    assert client_key == device_key
    assert decrypt_psk(device_key, "Home", encrypt_psk(client_key, 1, "Home", "not-a-real-password")) == "not-a-real-password"
