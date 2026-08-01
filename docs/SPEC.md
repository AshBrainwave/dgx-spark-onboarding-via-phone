# DGX Spark Phone Onboarding — Build Specification (PoC)

This repository implements the owner-provided build specification. The canonical brief is
maintained with the project conversation; implementation decisions and progress are tracked
in [`../STATUS.md`](../STATUS.md). The simulator-first build order is binding: hardware-free
steps 1–6 precede BLE, NetworkManager, SoftAP hardware, and DGX Spark bring-up.

Core rule: `api/handlers.py` and protocol types are transport agnostic. HTTP and BLE are
dumb pipes carrying the same versioned JSON envelope.

## Hardware networking

The production driver is `net/nm_driver.py`. It talks to NetworkManager on the system D-Bus,
scans access points, activates WPA2 profiles, and creates a 2.4 GHz shared-mode SoftAP. It
does not shell out to `nmcli`. A hardware invocation is `python -m sparkd_provision
--interface <wifi-interface>`; startup refuses an interface NetworkManager does not manage.
