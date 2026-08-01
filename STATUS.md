# DGX Spark Onboarding — Build Status

**Overall:** in_progress
**Current step:** 2 — Protocol security integration
**Updated:** 2026-08-01T07:55:00Z

## Milestones
- [x] 1. Repo skeleton + CI — clean-clone Python and browser test commands passed
- [x] 2. Protocol + framing — live HTTP crypto, QR-key comparison, shared fixtures, framing fuzz coverage, and cross-language crypto vectors are verified
- [x] 3. Mock driver + HTTP portal — captive probes and DNS answer generation are verified in the simulator
- [ ] 4. App screens — basic flow exists, but required screen components, QR scanning, and FSM are missing
- [ ] 5. Simulator (`v0.1-sim`)
- [ ] 6. Error screens (`v0.2-errors`)
- [ ] 7. BLE (`v0.3-ble`)
- [ ] 8. Hardware networking (`v0.4-hw`)

## Done since last update
- Initial README check-in (`f3c54e8`)
- Added skeleton, documentation, Apache-2.0 license, and CI (`fa6de1b`)
- Added transport-agnostic mock HTTP agent and basic framing coverage (`b9df34a`)
- Added simulator enrollment QR PNG and terminal rendering (`f551850`)
- Added actionable simulator error copy (`e661660`)
- Added unintegrated X25519/HKDF/AES-GCM protocol primitives (`5ea944f`)
- Configured verified GitHub SSH access and pushed `main` (`5ea944f`)
- Wired the live HTTP session to X25519/HKDF/AES-GCM and verified password-free request serialization (`7da6cc6`)
- Ran `agent/.venv/bin/python -m pytest`: 5 passed; ran browser contract test: 1 passed (`fa71e07`)
- Added verified captive-probe redirect handling and distinct malformed/unknown-operation errors (`5e94158`)
- Reproduced and fixed invalid AES-GCM tag handling; `agent/.venv/bin/python -m pytest`: 6 passed (`3d279cd`)
- Added shared fixed X25519/HKDF/AES-GCM vectors; Python: 7 passed, TypeScript: 2 passed (`c487660`)
- Added captive SoftAP DNS A-query response coverage; `agent/.venv/bin/python -m pytest`: 8 passed (`ee4f28b`)
- Verified a clean clone with `uv sync --extra dev`, Python tests (8 passed), `npm ci`, browser tests (2 passed), and TypeScript typecheck (pending commit)

## Blocked
- Nothing blocks simulator work.
- BLE validation requires the real Spark, a BlueZ-capable Linux Bluetooth adapter, and an Android phone. Hardware-networking validation requires the Spark and a supported Wi-Fi radio.

## Decisions I made that the spec didn't cover
- The simulator starts with HTTP on `localhost:8080`; production SoftAP and BLE remain deferred until their build-order steps.
- Hardware validation will start at the BLE and NetworkManager milestones, after the simulator contract is complete.

## Next
- Split the browser flow into the required screens and implement its finite-state machine.
