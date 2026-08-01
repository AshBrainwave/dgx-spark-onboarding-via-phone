#!/usr/bin/env bash
set -euo pipefail

# Install this during image construction. NetworkManager must own wlan0 before the
# service starts; sparkd-provision intentionally refuses unmanaged radios.
install -D -m 0644 deploy/sparkd-provision.service /etc/systemd/system/sparkd-provision.service
systemctl enable sparkd-provision.service
