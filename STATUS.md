# DGX Spark Onboarding — Build Status

**Overall:** in_progress
**Current step:** 1 — Repo skeleton + CI
**Updated:** 2026-08-01T00:00:00Z

## Milestones
- [ ] 1. Repo skeleton + CI
- [ ] 2. Protocol + framing + crypto (contract tests green)
- [ ] 3. Mock driver + HTTP portal
- [ ] 4. App screens
- [ ] 5. Simulator (`v0.1-sim`)
- [ ] 6. Error screens (`v0.2-errors`)
- [ ] 7. BLE (`v0.3-ble`)
- [ ] 8. Hardware networking (`v0.4-hw`)

## Done since last update
- Initial README check-in (`f3c54e8`)

## Blocked
- GitHub push is blocked: `git push -u origin main` received HTTP 403 for `AshBrainwave`. Local commits continue normally.
- Hardware availability, hosted deployment destination, account binding, and physical QR/display details need owner answers; simulator steps 1–6 are unaffected.

## Decisions I made that the spec didn't cover
- The simulator starts with HTTP on `localhost:8080`; production SoftAP and BLE remain deferred until their build-order steps.

## Next
- Add the repository skeleton, license, CI, and implementation documentation.
- Implement the shared protocol contract and its Python/TypeScript representations.
