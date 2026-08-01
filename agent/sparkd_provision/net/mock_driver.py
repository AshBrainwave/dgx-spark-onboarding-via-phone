from __future__ import annotations

import asyncio
import os

from sparkd_provision.net.driver import LinkStatus, NetDriver
from sparkd_provision.protocol.messages import Network


class MockDriver(NetDriver):
    def __init__(self) -> None:
        self.failure = os.getenv("SPARK_SIM_FAIL", "none").lower()
        self._status = LinkStatus()
        self._concurrent = os.getenv("SPARK_SIM_CONCURRENT_AP_STA", "1") == "1"
        self.networks = [
            Network("Malegaonkar-5G", "aa:bb:cc:dd:ee:01", -35, 4, "wpa2-psk", "5ghz", bands=["2.4ghz", "5ghz"]),
            Network("DGX Lab Guest", "aa:bb:cc:dd:ee:02", -51, 4, "open", "2.4ghz"),
            Network("Office Enterprise", "aa:bb:cc:dd:ee:03", -62, 3, "wpa2-enterprise", "5ghz", unsupported=True, reason="802.1X is not supported in this PoC"),
            Network("Hidden network", "aa:bb:cc:dd:ee:04", -76, 2, "wpa2-psk", "2.4ghz", hidden=True),
            Network("Far Away", "aa:bb:cc:dd:ee:05", -89, 1, "wpa2-psk", "2.4ghz"),
        ]

    @property
    def supports_concurrent_ap_sta(self) -> bool:
        return self._concurrent

    async def scan(self, force: bool = False) -> list[Network]:
        self._status = LinkStatus(phase="scanning")
        await asyncio.sleep(0.1)
        self._status = LinkStatus()
        return sorted(self.networks, key=lambda item: item.rssi, reverse=True)

    async def connect(self, ssid: str, psk: str, security: str, hidden: bool = False) -> None:
        async def progress() -> None:
            for phase in ("associating", "authenticating", "dhcp", "verifying_internet"):
                self._status = LinkStatus(phase=phase, ssid=ssid)
                await asyncio.sleep(0.7)
            code = {"auth": "WIFI_AUTH_FAILED", "dhcp": "WIFI_DHCP_FAILED", "timeout": "WIFI_SSID_NOT_FOUND", "weak": "WIFI_WEAK_SIGNAL", "captive": "WIFI_CAPTIVE_PORTAL"}.get(self.failure)
            if code:
                self._status = LinkStatus(phase="failed", ssid=ssid, err=code)
            else:
                self._status = LinkStatus(phase="online", ssid=ssid, ip="192.168.1.44", gw="192.168.1.1", dns="1.1.1.1", rssi=-47)
        asyncio.create_task(progress())

    async def status(self) -> LinkStatus:
        return self._status

    async def forget(self) -> None:
        self._status = LinkStatus()

    async def softap_up(self, ssid: str, psk: str) -> None: pass
    async def softap_down(self) -> None: pass
