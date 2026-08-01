# DGX Spark Onboarding — Build Status

**Overall:** in_progress
**Current step:** Part A2 — retest SoftAP on a separate virtual AP interface
**Updated:** 2026-08-01T23:36:25Z

## Verification matrix

| Verified on hardware | Verified in simulation only | Deferred (no Android) |
| --- | --- | --- |
| Spark aarch64/Python 3.12 portability gate; A1 NetworkManager ownership and AP+STA parser; Wi-Fi/Bluetooth rfkill state; A4 cached-airspace dedup/bands/6 GHz/security/hidden handling; Mac CoreBluetooth permission/preflight. | Protocol crypto/framing, mock driver, portal probes/DNS, app FSM/screens/error routes, simulator, NetworkManager/SoftAP implementation beyond A1/A4, BlueZ bridge, mDNS publisher, handoff recovery, lifecycle/reset logic, BLE central probe framing/codec self-test. | Chrome Web Bluetooth chooser, user-gesture handling, Location Services prompt, Chrome reconnect/service-cache behaviour, and Android SoftAP fallback/`.local` resolution. |

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
- Second guarded A2 activation proved the original concurrency implementation wrong: NetworkManager activated the AP on `wlP9s9`, replaced `Droid_IoT`, and dropped SSH. The one-shot 45-second recovery timer restored the exact STA UUID and reachability without polling. Fixed concurrent mode to create a separate bounded-name `__ap` interface, wait for NetworkManager ownership, activate an unsaved shared-mode AP profile on that device, and remove the profile/interface on teardown; all 18 Mac tests pass.
- First A2 activation failed safely before changing the radio: `dbus-fast` 5 rejected a Python `list[int]` for D-Bus signature `ay` (`SignatureBodyMismatchError`, requires `bytes`). Fixed both STA and SoftAP SSID construction behind a tested helper; the recovery timer was cancelled and `Droid_IoT` remained active.
- Root hardware identity discovery exposed the real platform serial `1983825003847`; hardware naming therefore uses suffix `3847` (`DGX-Spark-3847`), while unprivileged discovery correctly falls back to hostname.
- Fixed simulator identity leaking into hardware before A2: hardware mode now derives identity from `SPARK_SERIAL`, platform serial files, or hostname; `spark-0268` therefore drives AP name `DGX-Spark-0268`, BLE suffix `0268`, and mDNS name `dgx-spark-0268.local`, including after reset. Mac lint and all 17 tests pass.
- Verified A4 normalization on the Spark at `456d963`: lint and all 16 tests pass on aarch64; 33 entries normalize to 16 unique named SSIDs plus 17 hidden BSSIDs; `Droid` correctly aggregates 2.4/5/6 GHz and reports WPA3-SAE; 802.1X is explicitly unsupported. Forced scan and raw-dBm accuracy remain unverified.
- A4 read-only hardware comparison found that the original D-Bus scan emitted duplicate BSSIDs, lost hidden BSSIDs and multi-band information, mislabeled 6 GHz/WPA3/802.1X, and treated NetworkManager quality percent as dBm. Fixed scan normalization using the real Spark flag/frequency shapes, added WPA3 SAE connection selection, and added regression coverage; Mac lint and all 16 tests pass.
- Fixed hardware deployment defects found before A2: the package now installs a real `sparkd-provision` CLI; `first-boot.sh` discovers and validates the NetworkManager Wi-Fi interface instead of assuming `wlan0`; the isolated production venv includes GPIO support; and systemd uses the detected interface plus captive-portal port 80. The installer enables but does not start the service. Mac lint and all 15 tests pass.
- A1 hardware survey: NetworkManager owns connected `wlP9s9`; Wi-Fi and Bluetooth are enabled/unblocked; BlueZ is powered and supports peripheral role with 16 advertising instances; NetworkManager, Bluetooth, systemd-resolved, and Avahi are active/enabled.
- A1 AP+STA gate: the real wiphy advertises `#{ managed, P2P-client } <= 2, #{ AP } <= 1, #{ P2P-device } <= 1, total <= 3, #channels <= 1`. The production D-Bus driver selected `wlP9s9` and correctly reported `supports_concurrent_ap_sta=True`.
- A1 port survey: systemd-resolved listens only on loopback port 53; libvirt listens on `192.168.122.1:53`; ports 80/8080 are free. Binding DNS to a future AP address remains to be validated after AP activation.
- Established non-interactive SSH to `nbutme@192.168.68.87`: `spark-0268`, Ubuntu 24.04.4 LTS, aarch64, kernel `6.17.0-1029-nvidia`.
- Cloned pushed commit `76f39cb` onto the Spark over HTTPS, confirmed the authoritative spec SHA-256, installed `agent[dev]` into a repository-local Python 3.12.3 venv, and passed Spark-side lint plus all 14 tests.
- Restored GitHub push access by switching this Mac checkout from the unauthorized HTTPS identity (`mash-falcon`) to the existing SSH identity (`AshBrainwave`); pushed `main` through `fdd05bf`.
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
- Spark-side BLE advertising/GATT validation requires the agent to be deployed and advertising. The Mac side is ready and its CoreBluetooth permission is verified; no Android device is needed for Part C.
- Hardware-networking D-Bus activation, SoftAP, DNS, mDNS, and handoff behavior remain unrun pending non-interactive privilege.
- A4 forced rescan and exact RSSI validation remain blocked on privilege. NetworkManager exposes scan `Strength` as quality percent, not raw dBm; the corrected driver reports a conventional estimate until a raw NL80211 RSSI source is implemented and verified.
- The physical reset implementation needs the Spark carrier-board GPIO chip/line and an actual button press for validation. Real BlueZ advertising/GATT, AP recovery, Avahi publishing, and mutating D-Bus networking validation remain unrun.

## Decisions I made that the spec didn't cover
- The platform serial file is root-readable and contains `1983825003847`; hardware service identity uses it. Unprivileged tools fall back to hostname `spark-0268`, and `SPARK_SERIAL` remains the explicit image override.
- Preserved the protocol's `rssi` field by converting NetworkManager quality percent to an explicitly documented estimate (`quality / 2 - 100`) rather than continuing to mislabel `quality - 100` as real dBm. This remains a known spec gap pending raw NL80211 data.
- Used the complete `iw phy` output for the A1 gate because the hardware plan's suggested `sed` range stops after the first combination and hides the second, AP-capable combination.
- The simulator starts with HTTP on `localhost:8080`; production SoftAP uses NetworkManager shared mode when hardware mode is selected.
- The simulator accepts both documented uppercase `SPARK_SIM_FAIL` error codes and concise aliases. `WIFI_NO_INTERNET` proceeds to LAN-only success by design.

## Next
- Obtain non-interactive privilege for `nbutme`, install the hardware/systemd assets, and activate the A2 SoftAP with an SSH recovery guard.
- On the Spark/Mac: validate SoftAP, captive DNS/probes, real scan/join/error mappings, Avahi, and both handoff paths (Part A).
- On the Mac: run the reusable BLE central probe against the Spark; defer only Android browser-layer validation.
- Validate the non-concurrent recovery client on hardware: mDNS status polling, Android candidate-IP sweep/manual-IP fallback, and AP restoration within 20 seconds after every join failure (Priority 8).
- Validate the configured physical-reset GPIO button and systemd first-boot/state recovery/claim-lock/rate-limit behavior on the Spark (Priority 9).
