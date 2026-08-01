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

## Lifecycle and bring-up

Hardware mode restores a persisted SoftAP configuration and device lifecycle state from
`/var/lib/sparkd-provision/state.json`, mode 0600. The AP is WPA2, 2.4 GHz, shared IPv4,
and uses a twelve-character password from an unambiguous alphabet. Provisioning is open for
fifteen minutes and a factory reset reopens the window and rotates AP credentials. The
systemd unit and first-boot installer live in `deploy/` and `scripts/`.

The implementation still needs validation with a DGX Spark radio, physical reset button,
Android Chrome, and supported NetworkManager environment before any hardware milestone can
be marked complete.
