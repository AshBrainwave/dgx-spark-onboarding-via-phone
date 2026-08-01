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

## Provisioning lifecycle

Hardware mode persists lifecycle state in `/var/lib/sparkd-provision/state.json` with mode
`0600`: the provisioning-window timestamp, claim status, SHA-256 owner-token digest, device
name, and current SoftAP name/password. The home-network PSK is never written here; the AP
credential is required to restore a recoverable provisioning AP after reboot. The window
lasts fifteen minutes and factory reset reopens it and rotates the twelve-character SoftAP
password from an unambiguous alphabet. A configured active-low libgpiod reset button invokes
that same factory-reset operation, with one-second debounce.

The first `session.open` holds a 90-second single-claimer lock. A session releases it when
the Wi-Fi attempt reaches a failed status or it idles out. Each session permits five
`wifi.connect` attempts, with 0/1/3/7/15-second retry gates; extra calls return
`RATE_LIMITED` and premature retries return `RETRY_BACKOFF`.
