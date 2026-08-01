# DGX Spark Onboarding — Build Status

**Overall:** in_progress
**Current step:** Hardware bring-up — waiting for the Spark SSH target; Mac-side work continues
**Updated:** 2026-08-01T22:54:14Z

## Verification matrix

| Verified on hardware | Verified in simulation only | Deferred (no Android) |
| --- | --- | --- |
| Mac CoreBluetooth permission/preflight: 19 BLE advertisers detected. The Spark itself is not yet advertising. | Protocol crypto/framing, mock driver, portal probes/DNS, app FSM/screens/error routes, simulator, NetworkManager/SoftAP implementation, BlueZ bridge, mDNS publisher, handoff recovery, lifecycle/reset logic, BLE central probe framing/codec self-test. | Chrome Web Bluetooth chooser, user-gesture handling, Location Services prompt, Chrome reconnect/service-cache behaviour, and Android SoftAP fallback/`.local` resolution. |

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
- Added the reusable macOS `bleak` central probe for advertising, GATT properties, real-MTU framing, timeout NAKs, encrypted provisioning, and truncated ciphertext. Its framing/codec self-test passes; CoreBluetooth detected 19 nearby BLE devices, proving macOS permission is active. Full Spark-side C1–C5 remains unrun until deployment.
- Replaced the 35-line condensed `docs/SPEC.md` with the byte-identical 631-line authoritative build specification (`892edd4`).
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
- Added a BlueZ D-Bus GATT peripheral with advertised 128-bit service UUID, RX/TX/INFO characteristics, real gzip/base64url protocol bridge, ten-second reassembly NAKs, and radio-free bridge coverage. Added kernel wiphy AP+STA capability parsing plus non-concurrent handoff metadata and independent 20-second SoftAP recovery. Python lint/tests (13 passed), browser typecheck/tests (8 passed), and build passed (`7423753`).
- Added phone-side post-handoff discovery: mDNS first, bounded private-LAN candidate sweep for Android Chrome, and a manual LAN-IP fallback. Browser typecheck/tests (8 passed) and production build passed (`4f15223`).
- Added configurable, debounced active-low libgpiod physical-reset support. It runs the recovery-safe factory reset (clears claim/session, rotates AP password, restores SoftAP); Python lint/tests (14 passed), browser typecheck/tests (8 passed), and production build passed (`16d7896`; lock update `0ec19a9`).

## Blocked
- Nothing blocks simulator work.
- GitHub push is blocked: `git push origin main` failed with `remote: Permission to AshBrainwave/dgx-spark-onboarding-via-phone.git denied to mash-falcon` and HTTP 403. Local commits continue as required.
- Spark deployment and hardware Parts A/D are waiting for the operator to provide a key-authenticated `user@hostname` or `user@IP` SSH target.
- Spark-side BLE advertising/GATT validation requires the agent to be deployed and advertising. The Mac side is ready and its CoreBluetooth permission is verified; no Android device is needed for Part C.
- Hardware-networking validation requires the Spark SSH target, NetworkManager, and its Wi-Fi radio. D-Bus activation, SoftAP, DNS, mDNS, and handoff behavior remain unrun.
- The physical reset implementation needs the Spark carrier-board GPIO chip/line and an actual button press for validation. Real BlueZ advertising/GATT, NetworkManager AP+STA capability discovery, AP recovery, Avahi, and D-Bus networking validation remain blocked by this host's lack of Bluetooth and Wi-Fi hardware.
- Hardware bring-up cannot start from this workspace because no Spark hostname/IP or remote shell connection has been configured. The Mac/iPhone/Spark operator steps in the hardware brief require execution at those devices.

## Decisions I made that the spec didn't cover
- The simulator starts with HTTP on `localhost:8080`; production SoftAP uses NetworkManager shared mode when hardware mode is selected.
- The simulator accepts both documented uppercase `SPARK_SIM_FAIL` error codes and concise aliases. `WIFI_NO_INTERNET` proceeds to LAN-only success by design.

## Next
- On the Spark: deploy the repository, install `agent[dev,hardware]`, run the Python suite, then record the A1 NetworkManager/Bluetooth/rfkill/port-53 survey and logs.
- On the Spark/Mac: validate SoftAP, captive DNS/probes, real scan/join/error mappings, Avahi, and both handoff paths (Part A).
- On the Mac: run the reusable BLE central probe against the Spark; defer only Android browser-layer validation.
- Validate the non-concurrent recovery client on hardware: mDNS status polling, Android candidate-IP sweep/manual-IP fallback, and AP restoration within 20 seconds after every join failure (Priority 8).
- Validate the configured physical-reset GPIO button and systemd first-boot/state recovery/claim-lock/rate-limit behavior on the Spark (Priority 9).
