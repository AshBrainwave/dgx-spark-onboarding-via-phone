# DGX Spark Onboarding — Build Status

**Overall:** in_progress
**Current step:** 4 — App screens against mock
**Updated:** 2026-08-01T00:00:00Z

## Milestones
- [x] 1. Repo skeleton + CI
- [x] 2. Protocol + framing (contract foundation and tests green)
- [x] 3. Mock driver + HTTP portal
- [ ] 4. App screens ← in progress
- [ ] 5. Simulator (`v0.1-sim`)
- [ ] 6. Error screens (`v0.2-errors`)
- [ ] 7. BLE (`v0.3-ble`)
- [ ] 8. Hardware networking (`v0.4-hw`)

## Done since last update
- Initial README check-in (`f3c54e8`)
- Added skeleton, documentation, Apache-2.0 license, and CI (`fa6de1b`)
- Added transport-agnostic mock HTTP agent and framing test coverage (`b9df34a`)
- Added simulator enrollment QR PNG and terminal rendering (pending commit)

## Blocked
- GitHub push is blocked: `git push -u origin main` received HTTP 403 for `AshBrainwave`. Local commits continue normally.
- Hardware availability, hosted deployment destination, account binding, and physical QR/display details need owner answers; simulator steps 1–6 are unaffected.

## Decisions I made that the spec didn't cover
- The simulator starts with HTTP on `localhost:8080`; production SoftAP and BLE remain deferred until their build-order steps.

## Next
- Complete standalone routes and all distinct error screens.
- Add crypto vectors and shared TS/Python message contract tests.
