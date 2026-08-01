"""NetworkManager D-Bus driver.

This deliberately uses NetworkManager's D-Bus API rather than parsing ``nmcli`` output.
The driver is instantiated only on hardware; the simulator continues to use MockDriver.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from dbus_fast import BusType, Message, MessageType, Variant
from dbus_fast.aio import MessageBus

from sparkd_provision.net.driver import LinkStatus, NetDriver
from sparkd_provision.protocol.messages import Network

NM_BUS = "org.freedesktop.NetworkManager"
NM_PATH = "/org/freedesktop/NetworkManager"
NM_IFACE = "org.freedesktop.NetworkManager"
NM_DEVICE = "org.freedesktop.NetworkManager.Device"
NM_WIRELESS = "org.freedesktop.NetworkManager.Device.Wireless"
NM_SETTINGS = "org.freedesktop.NetworkManager.Settings"
NM_AP = "org.freedesktop.NetworkManager.AccessPoint"
PROPERTIES = "org.freedesktop.DBus.Properties"
WIFI_DEVICE_TYPE = 2


class NetworkManagerError(RuntimeError):
    """NetworkManager is missing, unavailable, or does not own the selected radio."""


def _variant(signature: str, value: Any) -> Variant:
    return Variant(signature, value)


class NetworkManagerDriver(NetDriver):
    def __init__(self, bus: MessageBus, device_path: str, interface: str) -> None:
        self.bus = bus
        self.device_path = device_path
        self.interface = interface
        self._status = LinkStatus()
        self._ap_connection: str | None = None
        self._concurrent_ap_sta = False

    @classmethod
    async def create(cls, interface: str | None = None) -> NetworkManagerDriver:
        bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
        driver = cls(bus, "", interface or "")
        devices = await driver._call(NM_PATH, NM_IFACE, "GetAllDevices")
        for path in devices:
            kind = await driver._property(path, NM_DEVICE, "DeviceType")
            name = await driver._property(path, NM_DEVICE, "Interface")
            if kind == WIFI_DEVICE_TYPE and (interface is None or name == interface):
                driver.device_path = path
                driver.interface = name
                break
        if not driver.device_path:
            wanted = f" '{interface}'" if interface else ""
            raise NetworkManagerError(
                f"NetworkManager does not own a wireless device{wanted}. "
                "Configure NetworkManager to manage the radio before starting sparkd-provision."
            )
        return driver

    async def _call(
        self,
        path: str,
        interface: str,
        member: str,
        signature: str = "",
        body: list[Any] | None = None,
    ) -> Any:
        reply = await self.bus.call(
            Message(
                destination=NM_BUS,
                path=path,
                interface=interface,
                member=member,
                signature=signature,
                body=body or [],
            )
        )
        if reply.message_type == MessageType.ERROR:
            raise NetworkManagerError(
                f"NetworkManager {member} failed: {reply.error_name}: {reply.body}"
            )
        return reply.body[0] if len(reply.body) == 1 else reply.body

    async def _property(self, path: str, interface: str, name: str) -> Any:
        value = await self._call(path, PROPERTIES, "Get", "ss", [interface, name])
        return value.value

    async def _properties(self, path: str, interface: str) -> dict[str, Any]:
        values = await self._call(path, PROPERTIES, "GetAll", "s", [interface])
        return {name: value.value for name, value in values.items()}

    @staticmethod
    def _ssid(value: bytes | bytearray | Iterable[int]) -> str:
        return bytes(value).decode("utf-8", errors="replace")

    async def scan(self, force: bool = False) -> list[Network]:
        self._status = LinkStatus(phase="scanning")
        if force:
            await self._call(self.device_path, NM_WIRELESS, "RequestScan", "a{sv}", [{}])
        access_points = await self._call(self.device_path, NM_WIRELESS, "GetAllAccessPoints")
        networks: list[Network] = []
        for path in access_points:
            values = await self._properties(path, NM_AP)
            ssid = self._ssid(values.get("Ssid", b""))
            if not ssid:
                continue
            frequency = int(values.get("Frequency", 0))
            band = "2.4ghz" if frequency < 5000 else "5ghz"
            protected = int(values.get("WpaFlags", 0)) or int(values.get("RsnFlags", 0))
            networks.append(
                Network(
                    ssid=ssid,
                    bssid=str(values.get("HwAddress", "")),
                    rssi=int(values.get("Strength", 0)) - 100,
                    bars=max(1, min(4, round(int(values.get("Strength", 0)) / 25))),
                    security="wpa2-psk" if protected else "open",
                    band=band,
                )
            )
        self._status = LinkStatus()
        return sorted(networks, key=lambda item: item.rssi, reverse=True)

    async def connect(self, ssid: str, psk: str, security: str, hidden: bool = False) -> None:
        if security == "wpa2-enterprise":
            raise NetworkManagerError("802.1X is not supported by this provisioning flow")
        self._status = LinkStatus(phase="associating", ssid=ssid)
        wifi: dict[str, Variant] = {"ssid": _variant("ay", list(ssid.encode()))}
        if hidden:
            wifi["hidden"] = _variant("b", True)
        settings: dict[str, dict[str, Variant]] = {
            "connection": {
                "id": _variant("s", f"DGX provisioning {ssid}"),
                "type": _variant("s", "802-11-wireless"),
                "autoconnect": _variant("b", False),
            },
            "802-11-wireless": wifi,
            "ipv4": {"method": _variant("s", "auto")},
            "ipv6": {"method": _variant("s", "ignore")},
        }
        if security != "open":
            settings["802-11-wireless-security"] = {
                "key-mgmt": _variant("s", "wpa-psk"),
                "psk": _variant("s", psk),
            }
        connection = await self._call(
            NM_PATH + "/Settings", NM_SETTINGS, "AddConnection", "a{sa{sv}}", [settings]
        )
        await self._call(
            NM_PATH, NM_IFACE, "ActivateConnection", "ooo", [connection, self.device_path, "/"]
        )

    async def status(self) -> LinkStatus:
        state = int(await self._property(self.device_path, NM_DEVICE, "State"))
        if state == 100:
            config = await self._property(self.device_path, NM_DEVICE, "Ip4Config")
            ip, gateway, dns = await self._ipv4_details(config)
            active_ap = await self._property(self.device_path, NM_WIRELESS, "ActiveAccessPoint")
            rssi = None
            if active_ap != "/":
                rssi = int(await self._property(active_ap, NM_AP, "Strength")) - 100
            self._status = LinkStatus(
                phase="online", ssid=self._status.ssid, ip=ip, gw=gateway, dns=dns, rssi=rssi
            )
        elif state == 60:
            self._status = LinkStatus(phase="authenticating", ssid=self._status.ssid)
        elif state == 70:
            self._status = LinkStatus(phase="dhcp", ssid=self._status.ssid)
        elif state in {40, 50, 80, 90}:
            self._status = LinkStatus(phase="associating", ssid=self._status.ssid)
        elif state == 120:
            self._status = LinkStatus(
                phase="failed", ssid=self._status.ssid, err=await self._failure_code()
            )
        return self._status

    async def _ipv4_details(self, config_path: str) -> tuple[str | None, str | None, str | None]:
        if config_path == "/":
            return None, None, None
        values = await self._properties(config_path, "org.freedesktop.NetworkManager.IP4Config")
        addresses = values.get("AddressData", [])
        ip = addresses[0].get("address") if addresses else None
        gateway = values.get("Gateway") or None
        nameservers = values.get("NameserverData", [])
        dns = nameservers[0].get("address") if nameservers else None
        return ip, gateway, dns

    async def _failure_code(self) -> str:
        # NetworkManager's numeric StateReason is intentionally collapsed to the
        # user-facing vocabulary rather than leaking backend-specific strings.
        reason = await self._property(self.device_path, NM_DEVICE, "StateReason")
        code = int(reason[1]) if isinstance(reason, (list, tuple)) and len(reason) > 1 else 0
        if code in {7, 8, 9, 11, 23, 24, 25}:
            return "WIFI_AUTH_FAILED"
        if code in {17, 20, 21}:
            return "WIFI_SSID_NOT_FOUND"
        if code in {5, 15, 22}:
            return "WIFI_DHCP_FAILED"
        return "WIFI_SSID_NOT_FOUND"

    async def forget(self) -> None:
        self._status = LinkStatus()

    async def softap_up(self, ssid: str, psk: str) -> None:
        settings = {
            "connection": {
                "id": _variant("s", "DGX Spark provisioning AP"),
                "type": _variant("s", "802-11-wireless"),
            },
            "802-11-wireless": {
                "ssid": _variant("ay", list(ssid.encode())),
                "mode": _variant("s", "ap"),
                "band": _variant("s", "bg"),
            },
            "802-11-wireless-security": {
                "key-mgmt": _variant("s", "wpa-psk"),
                "psk": _variant("s", psk),
            },
            "ipv4": {"method": _variant("s", "shared")},
            "ipv6": {"method": _variant("s", "ignore")},
        }
        connection = await self._call(
            NM_PATH + "/Settings", NM_SETTINGS, "AddConnection", "a{sa{sv}}", [settings]
        )
        self._ap_connection = await self._call(
            NM_PATH, NM_IFACE, "ActivateConnection", "ooo", [connection, self.device_path, "/"]
        )

    async def softap_down(self) -> None:
        if self._ap_connection:
            await self._call(NM_PATH, NM_IFACE, "DeactivateConnection", "o", [self._ap_connection])
            self._ap_connection = None

    @property
    def supports_concurrent_ap_sta(self) -> bool:
        return self._concurrent_ap_sta
