# DGX Spark Phone Onboarding

A phone-driven, simulator-first onboarding proof of concept for NVIDIA DGX Spark.

## Quickstart

Prerequisites: Python 3.11+, Node 20+, and `uv`.

```bash
git clone https://github.com/AshBrainwave/dgx-spark-onboarding-via-phone.git
cd dgx-spark-onboarding-via-phone
./sim/run_sim.sh
```

Open the Vite URL printed by the script. Set `SPARK_SIM_FAIL` to an error scenario such as
`auth`, `dhcp`, or `captive` to demo recovery states.

## Reset and recovery

The PoC re-advertises after a failed connection. On hardware, press the physical reset
button to reopen the provisioning window after it has expired.

See [the build status](STATUS.md) and [the specification](docs/SPEC.md).

## Hardware installation

Install the Python package and run `scripts/first-boot.sh` on the Spark image. The included
unit expects the Wi-Fi radio to be named `wlan0`; override the unit's `ExecStart` with the
NetworkManager-owned interface name when it differs. Device lifecycle data is in
`/var/lib/sparkd-provision/state.json` and is restricted to mode 0600.
