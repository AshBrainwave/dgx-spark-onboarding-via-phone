"""NetworkManager D-Bus driver.

This deliberately uses NetworkManager's D-Bus API rather than parsing ``nmcli`` output.
The driver is instantiated only on hardware; the simulator continues to use MockDriver.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Iterable
from dataclasses import replace
from typing import Any

from dbus_fast import BusType, Message, MessageType, Variant
from dbus_fast.aio import MessageBus

from sparkd_provision.net.capabilities import supports_concurrent_ap_sta
from sparkd_provision.net.driver import LinkStatus, NetDriver
from sparkd_provision.protocol.messages import Network

NM_BUS = "org.freedesktop.NetworkManager"
NM_PATH = "/org/freedesktop/NetworkManager"
NM_IFACE = "org.freedesktop.NetworkManager"
NM_DEVICE = "org.freedesktop.NetworkManager.Device"
NM_WIRELESS = "org.freedesktop.NetworkManager.Device.Wireless"
NM_SETTINGS = "org.freedesktop.NetworkManager.Settings"
NM_SETTINGS_CONNECTION = "org.freedesktop.NetworkManager.Settings.Connection"
NM_AP = "org.freedesktop.NetworkManager.AccessPoint"
PROPERTIES = "org.freedesktop.DBus.Properties"
WIFI_DEVICE_TYPE = 2
AP_FLAGS_PRIVACY = 0x00000001
SEC_KEY_MGMT_PSK = 0x00000100
SEC_KEY_MGMT_802_1X = 0x00000200
SEC_KEY_MGMT_SAE = 0x00000400
SEC_KEY_MGMT_OWE = 0x00000800
SEC_KEY_MGMT_OWE_TM = 0x00001000
SEC_KEY_MGMT_EAP_SUITE_B_192 = 0x00002000


def _band(frequency: int) -> str:
    if frequency >= 5925:
        return "6ghz"
    if frequency >= 4900:
        return "5ghz"
    return "2.4ghz"


def _channel(frequency: int) -> int | None:
    if frequency == 2484:
        return 14
    if 2412 <= frequency <= 2472:
        return (frequency - 2407) // 5
    if 5000 <= frequency < 5925:
        return (frequency - 5000) // 5
    if 5955 <= frequency <= 7115:
        return (frequency - 5950) // 5
    return None


def _quality_to_rssi(strength: int) -> int:
    quality = max(0, min(100, strength))
    return round(quality / 2 - 100)


def _security(flags: int, wpa_flags: int, rsn_flags: int) -> tuple[str, bool, str | None]:
    key_management = wpa_flags | rsn_flags
    if key_management & (SEC_KEY_MGMT_802_1X | SEC_KEY_MGMT_EAP_SUITE_B_192):
        return "wpa2-enterprise", True, "802.1X enterprise Wi-Fi is not supported by this PoC"
    if key_management & (SEC_KEY_MGMT_OWE | SEC_KEY_MGMT_OWE_TM):
        return "open", True, "Enhanced Open (OWE) is not supported by this PoC"
    if key_management & SEC_KEY_MGMT_SAE:
        return "wpa3-sae", False, None
    if key_management & SEC_KEY_MGMT_PSK:
        return "wpa2-psk", False, None
    if flags & AP_FLAGS_PRIVACY:
        return "wep", False, None
    return "open", False, None


def _network_from_properties(values: dict[str, Any], raw_rssi: float | None = None) -> Network:
    ssid = NetworkManagerDriver._ssid(values.get("Ssid", b""))
    strength = max(0, min(100, int(values.get("Strength", 0))))
    # NetworkManager exposes quality percent, not dBm. Its conventional inverse
    # maps 0..100 quality to approximately -100..-50 dBm.
    rssi = round(raw_rssi) if raw_rssi is not None else _quality_to_rssi(strength)
    if rssi >= -60:
        bars = 4
    elif rssi >= -70:
        bars = 3
    elif rssi >= -80:
        bars = 2
    elif rssi >= -90:
        bars = 1
    else:
        bars = 0
    security, unsupported, reason = _security(
        int(values.get("Flags", 0)),
        int(values.get("WpaFlags", 0)),
        int(values.get("RsnFlags", 0)),
    )
    return Network(
        ssid=ssid,
        bssid=str(values.get("HwAddress", "")),
        rssi=rssi,
        bars=bars,
        security=security,
        band=_band(int(values.get("Frequency", 0))),
        hidden=not bool(ssid),
        unsupported=unsupported,
        reason=reason,
    )


def _deduplicate_networks(networks: list[Network]) -> list[Network]:
    strongest: dict[str, Network] = {}
    bands: dict[str, set[str]] = {}
    for network in networks:
        # Empty SSIDs reveal no identity to deduplicate on, so retain each BSSID.
        key = network.ssid if network.ssid else f"\0{network.bssid}"
        bands.setdefault(key, set()).add(network.band)
        if key not in strongest or network.rssi > strongest[key].rssi:
            strongest[key] = network
    band_order = {"2.4ghz": 0, "5ghz": 1, "6ghz": 2}
    normalized = []
    for key, network in strongest.items():
        seen_bands = sorted(bands[key], key=band_order.__getitem__)
        normalized.append(replace(network, bands=seen_bands if len(seen_bands) > 1 else None))
    return sorted(normalized, key=lambda item: item.rssi, reverse=True)


def _raw_rssi_from_iw(output: str) -> dict[str, float]:
    readings: dict[str, float] = {}
    bssid: str | None = None
    for line in output.splitlines():
        match = re.match(r"^BSS ([0-9a-fA-F:]{17})(?:\(|\s|$)", line)
        if match:
            bssid = match.group(1).lower()
            continue
        match = re.match(r"^\s*signal:\s*(-?\d+(?:\.\d+)?)\s+dBm", line)
        if bssid and match:
            readings[bssid] = float(match.group(1))
    return readings


class NetworkManagerError(RuntimeError):
    """NetworkManager is missing, unavailable, or does not own the selected radio."""


def _variant(signature: str, value: Any) -> Variant:
    return Variant(signature, value)


def _unbox(value: Any) -> Any:
    if isinstance(value, Variant):
        return _unbox(value.value)
    if isinstance(value, dict):
        return {key: _unbox(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_unbox(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_unbox(item) for item in value)
    return value


def _ssid_variant(ssid: str) -> Variant:
    return _variant("ay", ssid.encode())


class NetworkManagerDriver(NetDriver):
    def __init__(self, bus: MessageBus, device_path: str, interface: str) -> None:
        self.bus = bus
        self.device_path = device_path
        self.interface = interface
        self._status = LinkStatus()
        self._ap_connection: str | None = None
        self._ap_profile: str | None = None
        self._ap_interface: str | None = None
        self._ap_device_path: str | None = None
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
        driver._concurrent_ap_sta = await driver._detect_concurrent_ap_sta()
        return driver

    async def _detect_concurrent_ap_sta(self) -> bool:
        """Read NL80211's wiphy combinations without changing radio state."""
        try:
            process = await asyncio.create_subprocess_exec(
                "iw", "dev", self.interface, "info", stdout=asyncio.subprocess.PIPE
            )
            info, _ = await process.communicate()
            phy = next(
                (
                    line.split()[1]
                    for line in info.decode().splitlines()
                    if line.strip().startswith("wiphy ")
                ),
                None,
            )
            if phy is None:
                return False
            process = await asyncio.create_subprocess_exec(
                "iw", "phy", f"phy{phy}", "info", stdout=asyncio.subprocess.PIPE
            )
            output, _ = await process.communicate()
            return process.returncode == 0 and supports_concurrent_ap_sta(output.decode())
        except (FileNotFoundError, OSError):
            return False

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
        return {name: _unbox(value) for name, value in values.items()}

    @staticmethod
    def _ssid(value: bytes | bytearray | Iterable[int]) -> str:
        return bytes(value).decode("utf-8", errors="replace")

    async def scan(self, force: bool = False) -> list[Network]:
        self._status = LinkStatus(phase="scanning")
        if force:
            previous_scan = int(await self._property(self.device_path, NM_WIRELESS, "LastScan"))
            await self._call(self.device_path, NM_WIRELESS, "RequestScan", "a{sv}", [{}])
            for _ in range(100):
                if int(await self._property(self.device_path, NM_WIRELESS, "LastScan")) > previous_scan:
                    break
                await asyncio.sleep(0.1)
        access_points = await self._call(self.device_path, NM_WIRELESS, "GetAllAccessPoints")
        raw_rssi = await self._raw_rssi()
        networks: list[Network] = []
        for path in access_points:
            values = await self._properties(path, NM_AP)
            bssid = str(values.get("HwAddress", "")).lower()
            networks.append(_network_from_properties(values, raw_rssi.get(bssid)))
        self._status = LinkStatus()
        return _deduplicate_networks(networks)

    async def _raw_rssi(self) -> dict[str, float]:
        try:
            process = await asyncio.create_subprocess_exec(
                "iw",
                "dev",
                self.interface,
                "scan",
                "dump",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError:
            return {}
        output, _ = await process.communicate()
        if process.returncode:
            return {}
        return _raw_rssi_from_iw(output.decode(errors="replace"))

    async def connect(self, ssid: str, psk: str, security: str, hidden: bool = False) -> None:
        if security == "wpa2-enterprise":
            raise NetworkManagerError("802.1X is not supported by this provisioning flow")
        self._status = LinkStatus(phase="associating", ssid=ssid)
        wifi: dict[str, Variant] = {"ssid": _ssid_variant(ssid)}
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
                "key-mgmt": _variant("s", "sae" if security == "wpa3-sae" else "wpa-psk"),
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
                rssi = _quality_to_rssi(int(await self._property(active_ap, NM_AP, "Strength")))
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

    async def softap_up(self, ssid: str, psk: str) -> str:
        ap_device = self.device_path
        if self.supports_concurrent_ap_sta:
            ap_device = await self._ensure_ap_device()
        self._ap_device_path = ap_device
        wifi_settings = {
            "ssid": _ssid_variant(ssid),
            "mode": _variant("s", "ap"),
            "band": _variant("s", "bg"),
        }
        if self.supports_concurrent_ap_sta:
            active_ap = await self._property(self.device_path, NM_WIRELESS, "ActiveAccessPoint")
            if active_ap != "/":
                frequency = int(await self._property(active_ap, NM_AP, "Frequency"))
                channel = _channel(frequency)
                if channel is not None:
                    wifi_settings["band"] = _variant("s", "bg" if frequency < 5000 else "a")
                    wifi_settings["channel"] = _variant("u", channel)
        settings = {
            "connection": {
                "id": _variant("s", "DGX Spark provisioning AP"),
                "type": _variant("s", "802-11-wireless"),
                "autoconnect": _variant("b", False),
            },
            "802-11-wireless": wifi_settings,
            "802-11-wireless-security": {
                "key-mgmt": _variant("s", "wpa-psk"),
                "psk": _variant("s", psk),
            },
            "ipv4": {"method": _variant("s", "shared")},
            "ipv6": {"method": _variant("s", "ignore")},
        }
        if self._ap_interface:
            settings["connection"]["interface-name"] = _variant("s", self._ap_interface)
        try:
            self._ap_profile = await self._call(
                NM_PATH + "/Settings",
                NM_SETTINGS,
                "AddConnectionUnsaved",
                "a{sa{sv}}",
                [settings],
            )
            self._ap_connection = await self._call(
                NM_PATH,
                NM_IFACE,
                "ActivateConnection",
                "ooo",
                [self._ap_profile, ap_device, "/"],
            )
            for _ in range(150):
                state = int(await self._property(ap_device, NM_DEVICE, "State"))
                if state == 100:
                    config = await self._property(ap_device, NM_DEVICE, "Ip4Config")
                    address, _, _ = await self._ipv4_details(config)
                    if address:
                        return address
                if state == 120:
                    raise NetworkManagerError("provisioning AP activation failed")
                await asyncio.sleep(0.1)
            raise NetworkManagerError("provisioning AP did not acquire an IPv4 address")
        except NetworkManagerError:
            try:
                await self.softap_down()
            except NetworkManagerError:
                pass
            raise

    async def softap_down(self) -> None:
        if self._ap_connection:
            await self._call(NM_PATH, NM_IFACE, "DeactivateConnection", "o", [self._ap_connection])
            self._ap_connection = None
        if self._ap_profile:
            await self._call(self._ap_profile, NM_SETTINGS_CONNECTION, "Delete")
            self._ap_profile = None
        if self._ap_interface:
            await self._run_iw("dev", self._ap_interface, "del")
            self._ap_interface = None
        self._ap_device_path = None

    async def _ensure_ap_device(self) -> str:
        self._ap_interface = f"{self.interface[:11]}-ap"
        device = await self._device_path(self._ap_interface)
        if device and int(await self._property(device, NM_DEVICE, "State")) >= 30:
            return device
        if not device:
            await self._run_iw(
                "dev", self.interface, "interface", "add", self._ap_interface, "type", "__ap"
            )
        for _ in range(50):
            device = await self._device_path(self._ap_interface)
            if device and int(await self._property(device, NM_DEVICE, "State")) >= 30:
                return device
            await asyncio.sleep(0.1)
        raise NetworkManagerError(
            f"NetworkManager did not claim concurrent AP interface {self._ap_interface}"
        )

    async def _device_path(self, interface: str) -> str | None:
        devices = await self._call(NM_PATH, NM_IFACE, "GetAllDevices")
        for path in devices:
            if await self._property(path, NM_DEVICE, "Interface") == interface:
                return path
        return None

    @staticmethod
    async def _run_iw(*arguments: str) -> None:
        try:
            process = await asyncio.create_subprocess_exec(
                "iw",
                *arguments,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as exc:
            raise NetworkManagerError(f"could not execute iw: {exc}") from exc
        output, error_output = await process.communicate()
        if process.returncode:
            detail = (error_output or output).decode(errors="replace").strip()
            raise NetworkManagerError(f"iw {' '.join(arguments)} failed: {detail}")

    @property
    def supports_concurrent_ap_sta(self) -> bool:
        return self._concurrent_ap_sta
