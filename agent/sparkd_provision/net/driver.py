from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from sparkd_provision.protocol.messages import Network


@dataclass(frozen=True)
class LinkStatus:
    phase: str = "idle"
    ssid: str | None = None
    ip: str | None = None
    gw: str | None = None
    dns: str | None = None
    rssi: int | None = None
    err: str | None = None


class NetDriver(ABC):
    @abstractmethod
    async def scan(self, force: bool = False) -> list[Network]: ...

    @abstractmethod
    async def connect(self, ssid: str, psk: str, security: str, hidden: bool = False) -> None: ...

    @abstractmethod
    async def status(self) -> LinkStatus: ...

    @abstractmethod
    async def forget(self) -> None: ...

    @abstractmethod
    async def softap_up(self, ssid: str, psk: str) -> None: ...

    @abstractmethod
    async def softap_down(self) -> None: ...

    @property
    @abstractmethod
    def supports_concurrent_ap_sta(self) -> bool: ...
