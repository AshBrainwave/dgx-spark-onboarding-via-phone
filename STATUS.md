# DGX Spark Onboarding — Build Status

**Overall:** in_progress
**Current step:** 5 — Simulator completion
**Updated:** 2026-08-01T21:43:00Z

## Milestones
- [x] 1. Repo skeleton + CI — clean-clone Python and browser test commands passed
- [x] 2. Protocol + framing — live HTTP crypto, QR-key comparison, shared fixtures, framing fuzz coverage, and cross-language crypto vectors are verified
- [x] 3. Mock driver + HTTP portal — captive probes and DNS answer generation are verified in the simulator
- [x] 4. App screens — guarded FSM, ten standalone review routes, QR scanner/manual fallback, progress UI, and error routes are typechecked and unit tested
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
- Built the app screen flow and error taxonomy; `npm test -- --run` (5 passed), `npm run typecheck`, and `npm run build` passed
- Extended mock failure injection for all Wi-Fi outcomes and session/transport failures; simulator launch succeeded with `SPARK_SIM_FAIL=WIFI_AUTH_FAILED SPARK_SIM_CONCURRENT_AP_STA=0`

## Blocked
- Nothing blocks simulator work.
- BLE validation requires the real Spark, a BlueZ-capable Linux Bluetooth adapter, and an Android phone. Hardware-networking validation requires the Spark and a supported Wi-Fi radio.

## Decisions I made that the spec didn't cover
- The simulator starts with HTTP on `localhost:8080`; production SoftAP and BLE remain deferred until their build-order steps.
- Hardware validation will start at the BLE and NetworkManager milestones, after the simulator contract is complete.

## Next
- Verify the simulator from a genuinely fresh temporary clone in a browser, including the default flow and every `SPARK_SIM_FAIL` error route; only then tag `v0.1-sim` and `v0.2-errors`.
- Implement BLE loopback framing and then validate against Android Chrome and the real Spark (Priority 6).
- Implement NetworkManager D-Bus driver, AP mode, mDNS, and real captive portal behavior (Priority 7).
- Implement runtime AP+STA handoff and recovery behavior (Priority 8).
- Implement persistent first-boot/systemd provisioning lifecycle, physical reset, claim lock, and rate limits (Priority 9).
