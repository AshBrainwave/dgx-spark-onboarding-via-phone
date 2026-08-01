# Security model

The Wi-Fi PSK is encrypted at the application layer: X25519 ECDH, HKDF-SHA256 with info
`dgx-spark-prov-v1`, then AES-256-GCM with SSID as AAD. The QR code pins the device public
key; a key reported over the transport that differs from the QR key aborts provisioning.

The device accepts provisioning only during its 15-minute provisioning window. The first
session locks ownership for 90 seconds. Owner tokens are generated randomly and only their
hash is persisted. PSKs are never logged, persisted outside NetworkManager, or returned by
status APIs.

Out of scope: hardware attestation, portal TLS, and cloud account binding.

Malformed or stale AES-GCM ciphertext (including a key rotation between retries) returns
`INVALID_CIPHERTEXT`; it must never escape as an HTTP 500. This also makes truncated BLE
reassembly safe to report as a protocol error.
