# DGX Spark Phone Onboarding — Build Specification (PoC)

This repository implements the owner-provided build specification. The canonical brief is
maintained with the project conversation; implementation decisions and progress are tracked
in [`../STATUS.md`](../STATUS.md). The simulator-first build order is binding: hardware-free
steps 1–6 precede BLE, NetworkManager, SoftAP hardware, and DGX Spark bring-up.

Core rule: `api/handlers.py` and protocol types are transport agnostic. HTTP and BLE are
dumb pipes carrying the same versioned JSON envelope.
