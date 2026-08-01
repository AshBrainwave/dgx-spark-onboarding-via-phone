"""Protocol v1 application-layer key agreement and PSK encryption."""

from __future__ import annotations

import base64

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

INFO = b"dgx-spark-prov-v1"


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def unb64url(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def generate_keypair() -> tuple[X25519PrivateKey, str]:
    private = X25519PrivateKey.generate()
    return private, b64url(private.public_key().public_bytes_raw())


def derive_key(private: X25519PrivateKey, peer_public_b64: str, client_nonce: str, device_nonce: str) -> bytes:
    shared = private.exchange(X25519PublicKey.from_public_bytes(unb64url(peer_public_b64)))
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=(client_nonce + device_nonce).encode(), info=INFO).derive(shared)


def encrypt_psk(key: bytes, counter: int, ssid: str, psk: str) -> str:
    nonce = counter.to_bytes(12, "big")
    return b64url(nonce + AESGCM(key).encrypt(nonce, psk.encode(), ssid.encode()))


def decrypt_psk(key: bytes, ssid: str, ciphertext: str) -> str:
    raw = unb64url(ciphertext)
    return AESGCM(key).decrypt(raw[:12], raw[12:], ssid.encode()).decode()
