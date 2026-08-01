# DGX Spark Onboarding — Build Status

**Overall:** in_progress
**Current step:** 7 — BLE hardware validation is blocked; browser transport and device lifecycle implementation added
**Updated:** 2026-08-01T21:56:00Z

## Milestones
- [x] 1. Repo skeleton + CI — clean-clone Python and browser test commands passed
- [x] 2. Protocol + framing — live HTTP crypto, QR-key comparison, shared fixtures, framing fuzz coverage, and cross-language crypto vectors are verified
- [x] 3. Mock driver + HTTP portal — captive probes and DNS answer generation are verified in the simulator
- [x] 4. App screens — guarded FSM, ten standalone review routes, QR scanner/manual fallback, progress UI, and error routes are typechecked and unit tested
- [x] 5. Simulator (`v0.1-sim`) — fresh-clone launch and all mock error paths verified; tagged
- [x] 6. Error screens (`v0.2-errors`) — standalone code routes and mock injection verified; tagged
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
- Fresh temporary clone launch succeeded: it created a new Python venv, installed dependencies, printed QR PNG/ASCII, and served the simulator. Browser BLE framing loopback tests now pass (8 browser tests total).
- Verified all documented simulator Wi-Fi error codes directly and as `?screen=error&error=<CODE>` review routes; Python tests: 9 passed, browser tests: 8 passed, typecheck/build passed. Tagged and pushed `v0.1-sim` and `v0.2-errors` (`22158e6`).
- Added the production NetworkManager D-Bus driver (`dbus-fast`), including startup ownership detection, access-point scan, WPA2 profile activation, and a 2.4 GHz shared SoftAP profile. Lint, 9 Python tests, 8 browser tests, and TypeScript typecheck passed (`8d001f5`).
- Added durable provisioning lifecycle state, first-boot systemd assets, claim/window/backoff enforcement, real NetworkManager IPv4 status extraction, and a browser Web Bluetooth GATT transport. Python lint/tests (9 passed), browser typecheck/tests (8 passed), and build passed (`1b1192d`).
- Added an Avahi D-Bus publisher for `_dgx-spark._tcp.local` after an online status; lint, Python tests (9 passed), browser typecheck, and browser tests (8 passed) (`ae4b6a0`).

## Blocked
- Nothing blocks simulator work.
- BLE validation requires the real Spark, a BlueZ-capable Linux Bluetooth adapter, and an Android phone. This workspace's `bluetoothctl show` fails with `Unable to open mgmt_socket`; no usable adapter is present.
- Hardware-networking validation requires the Spark, NetworkManager, and a supported Wi-Fi radio. None is available in this workspace, so D-Bus activation, SoftAP, DNS, mDNS, and handoff behavior cannot yet be run.
- The physical-reset GPIO wiring, BlueZ GATT peripheral, Avahi publisher, runtime AP+STA capability detection, and handoff/recovery path are not yet implemented. They need a Spark-specific hardware interface and cannot be responsibly guessed from this radio-less host.

## Decisions I made that the spec didn't cover
- The simulator starts with HTTP on `localhost:8080`; production SoftAP uses NetworkManager shared mode when hardware mode is selected.
- The simulator accepts both documented uppercase `SPARK_SIM_FAIL` error codes and concise aliases. `WIFI_NO_INTERNET` proceeds to LAN-only success by design.

## Next
- Implement the actual Web Bluetooth GATT transport (request-device gesture, advertised service filter, characteristics, gzip/base64url framing, reconnect) and BLE peripheral, then validate against Android Chrome and the real Spark (Priority 6). The radio-free framing loopback is already tested.
- Implement the Linux BlueZ GATT peripheral (advertisement UUID/name, CTRL RX/TX/INFO, ten-second NAK handling) and validate it with Android Chrome and the real Spark (Priority 6). The browser transport is implemented; validation remains blocked by hardware.
- Complete and unit-test the NetworkManager driver: map NM state reasons to the full Wi-Fi taxonomy, add Avahi mDNS, connect DNS/captive behavior to the AP address, and validate profile persistence/status on a supported radio (Priority 7).
- Implement runtime wiphy AP+STA detection, non-concurrent handoff/recovery within 20 seconds, mDNS/IP-sweep client reconnection, and test on hardware (Priority 8).
- Implement the physical-reset GPIO integration and validate systemd first-boot/state recovery/claim-lock/rate-limit behavior on the Spark (Priority 9).
