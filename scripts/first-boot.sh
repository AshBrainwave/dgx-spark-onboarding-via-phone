#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Run this installer as root: sudo scripts/first-boot.sh [wifi-interface]" >&2
  exit 1
fi

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
interface="${SPARK_WIFI_INTERFACE:-${1:-}}"
if [[ -z ${interface} ]]; then
  interface="$(nmcli -t -f DEVICE,TYPE device status | awk -F: '$2 == "wifi" { print $1; exit }')"
fi
if [[ ! ${interface} =~ ^[[:alnum:]_.:-]+$ ]]; then
  echo "Could not determine a safe NetworkManager Wi-Fi interface name" >&2
  exit 1
fi
if ! nmcli -t -f DEVICE,TYPE device status | grep -Fqx "${interface}:wifi"; then
  echo "NetworkManager does not own Wi-Fi interface ${interface}" >&2
  exit 1
fi

runtime_root=/opt/dgx-spark-onboarding
python3 -m venv "${runtime_root}/venv"
"${runtime_root}/venv/bin/python" -m pip install "${repo_root}/agent[hardware]"

install -D -m 0644 "${repo_root}/deploy/sparkd-provision.service" \
  /etc/systemd/system/sparkd-provision.service
environment_file="$(mktemp)"
trap 'rm -f "${environment_file}"' EXIT
printf 'SPARK_WIFI_INTERFACE=%s\n' "${interface}" > "${environment_file}"
install -D -m 0644 "${environment_file}" /etc/default/sparkd-provision
systemctl daemon-reload
systemctl enable sparkd-provision.service
echo "Installed sparkd-provision for ${interface}; the service is enabled but not started."
