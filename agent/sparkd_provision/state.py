"""Durable provisioning state.

The file deliberately contains no Wi-Fi credentials or owner token: NetworkManager owns
the credential, and only a SHA-256 digest of a claim token is retained.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class DeviceState:
    provision_opened_at: str
    ap_ssid: str = "DGX-Spark-0001"
    ap_psk: str = ""
    claimed: bool = False
    owner_token_hash: str | None = None
    name: str = "DGX Spark"


class StateStore:
    def __init__(self, path: Path | None = None, ap_ssid: str = "DGX-Spark-0001") -> None:
        self.path = path
        self.ap_ssid = ap_ssid
        now = datetime.now(UTC).isoformat()
        self.state = DeviceState(
            provision_opened_at=now, ap_ssid=self.ap_ssid, ap_psk=self._ap_password()
        )
        if path and path.exists():
            self.state = DeviceState(**json.loads(path.read_text()))

    def save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(asdict(self.state), sort_keys=True))
        os.chmod(temporary, 0o600)
        temporary.replace(self.path)

    def reset(self) -> None:
        self.state = DeviceState(
            provision_opened_at=datetime.now(UTC).isoformat(),
            ap_ssid=self.ap_ssid,
            ap_psk=self._ap_password(),
        )
        self.save()

    @staticmethod
    def _ap_password() -> str:
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
        return "".join(secrets.choice(alphabet) for _ in range(12))

    @property
    def provisioning_open(self) -> bool:
        opened = datetime.fromisoformat(self.state.provision_opened_at)
        return (datetime.now(UTC) - opened).total_seconds() < 15 * 60

    def claim(self, token: str) -> None:
        self.state.claimed = True
        self.state.owner_token_hash = hashlib.sha256(token.encode()).hexdigest()
        self.save()

    def token_matches(self, token: object) -> bool:
        if not isinstance(token, str) or not self.state.owner_token_hash:
            return False
        return hashlib.sha256(token.encode()).hexdigest() == self.state.owner_token_hash
