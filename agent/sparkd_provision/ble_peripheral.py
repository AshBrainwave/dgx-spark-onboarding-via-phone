"""BlueZ GATT peripheral and protocol bridge for DGX Spark provisioning.

The classes are deliberately kept separate: :class:`BleProtocolBridge` is entirely
radio-free and unit-testable, while :class:`BluezPeripheral` is the small adapter
which exports BlueZ's D-Bus GATT and advertisement objects on hardware.
"""
# ruff: noqa: F821

import asyncio
import base64
import gzip
import json
from collections.abc import Awaitable, Callable
from typing import Any

from dbus_fast import BusType, Message, MessageType
from dbus_fast.aio import MessageBus
from dbus_fast.service import PropertyAccess, ServiceInterface, dbus_property, method

from sparkd_provision.api.handlers import Handlers
from sparkd_provision.protocol.framing import Reassembler, fragment
from sparkd_provision.protocol.messages import error

SERVICE_UUID = "a66a068e-b4b7-4df6-a00d-7e2c04a36f26"
CTRL_RX_UUID = "a66a068f-b4b7-4df6-a00d-7e2c04a36f26"
CTRL_TX_UUID = "a66a0690-b4b7-4df6-a00d-7e2c04a36f26"
INFO_UUID = "a66a0691-b4b7-4df6-a00d-7e2c04a36f26"
BLUEZ = "org.bluez"
ROOT = "/org/dgx_spark/provision"


def _encode(message: dict[str, Any]) -> bytes:
    raw = json.dumps(message, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(gzip.compress(raw)).rstrip(b"=")


def _decode(payload: bytes) -> dict[str, Any]:
    padded = payload + b"=" * (-len(payload) % 4)
    decoded = gzip.decompress(base64.urlsafe_b64decode(padded))
    value = json.loads(decoded)
    if not isinstance(value, dict):
        raise TypeError("BLE envelope must be an object")
    return value


class BleProtocolBridge:
    """Translate raw ATT frames to transport-neutral agent calls."""

    def __init__(self, handlers: Handlers, send: Callable[[bytes], Awaitable[None]]) -> None:
        self.handlers = handlers
        self.send = send
        self.reassembler = Reassembler()

    async def receive(self, frame: bytes) -> None:
        complete = self.reassembler.add(frame)
        if complete is None:
            return
        message_id, payload = complete
        try:
            result = await self.handlers.handle(_decode(payload))
        except (ValueError, TypeError, OSError) as exc:
            result = error("", "BAD_REQUEST", detail={"reason": str(exc)})
        await self._send(message_id, result)

    async def expire(self) -> None:
        for message_id in self.reassembler.expire():
            await self._send(message_id, error("", "BLE_REASSEMBLY_TIMEOUT"))

    async def _send(self, message_id: int, response: dict[str, Any]) -> None:
        for frame in fragment(_encode(response), message_id):
            await self.send(frame)


class _Advertisement(ServiceInterface):
    def __init__(self, local_name: str) -> None:
        super().__init__("org.bluez.LEAdvertisement1")
        self.local_name = local_name

    @method()
    def Release(self) -> None:
        pass

    @dbus_property(access=PropertyAccess.READ)
    def Type(self) -> "s":
        return "peripheral"

    @dbus_property(access=PropertyAccess.READ)
    def ServiceUUIDs(self) -> "as":
        return [SERVICE_UUID]

    @dbus_property(access=PropertyAccess.READ)
    def LocalName(self) -> "s":
        return self.local_name


class _Service(ServiceInterface):
    def __init__(self) -> None:
        super().__init__("org.bluez.GattService1")

    @dbus_property(access=PropertyAccess.READ)
    def UUID(self) -> "s":
        return SERVICE_UUID

    @dbus_property(access=PropertyAccess.READ)
    def Primary(self) -> "b":
        return True


class _RxCharacteristic(ServiceInterface):
    def __init__(self, receive: Callable[[bytes], Awaitable[None]]) -> None:
        super().__init__("org.bluez.GattCharacteristic1")
        self.receive = receive

    @method()
    def WriteValue(self, value: "ay", options: "a{sv}") -> None:
        del options
        asyncio.create_task(self.receive(bytes(value)))

    @dbus_property(access=PropertyAccess.READ)
    def UUID(self) -> "s":
        return CTRL_RX_UUID

    @dbus_property(access=PropertyAccess.READ)
    def Service(self) -> "o":
        return ROOT + "/service0"

    @dbus_property(access=PropertyAccess.READ)
    def Flags(self) -> "as":
        return ["write-without-response"]


class _TxCharacteristic(ServiceInterface):
    def __init__(self) -> None:
        super().__init__("org.bluez.GattCharacteristic1")
        self.notifying = False
        self.value = b""

    @method()
    def StartNotify(self) -> None:
        self.notifying = True

    @method()
    def StopNotify(self) -> None:
        self.notifying = False

    @dbus_property(access=PropertyAccess.READ)
    def UUID(self) -> "s":
        return CTRL_TX_UUID

    @dbus_property(access=PropertyAccess.READ)
    def Service(self) -> "o":
        return ROOT + "/service0"

    @dbus_property(access=PropertyAccess.READ)
    def Flags(self) -> "as":
        return ["notify"]

    @dbus_property(access=PropertyAccess.READ)
    def Notifying(self) -> "b":
        return self.notifying

    @dbus_property(access=PropertyAccess.READ)
    def Value(self) -> "ay":
        return self.value

    async def notify(self, frame: bytes) -> None:
        if self.notifying:
            self.value = bytes(frame)
            self.emit_properties_changed({"Value": self.value})


class _InfoCharacteristic(ServiceInterface):
    def __init__(self, handlers: Handlers) -> None:
        super().__init__("org.bluez.GattCharacteristic1")
        self.handlers = handlers

    @method()
    def ReadValue(self, options: "a{sv}") -> "ay":
        del options
        return json.dumps({"serial": self.handlers.serial, "pubkey": self.handlers.device_public}).encode()

    @dbus_property(access=PropertyAccess.READ)
    def UUID(self) -> "s":
        return INFO_UUID

    @dbus_property(access=PropertyAccess.READ)
    def Service(self) -> "o":
        return ROOT + "/service0"

    @dbus_property(access=PropertyAccess.READ)
    def Flags(self) -> "as":
        return ["read"]


class BluezPeripheral:
    """Export and advertise the fixed GATT profile through BlueZ system D-Bus."""

    def __init__(self, bus: MessageBus, adapter: str, handlers: Handlers) -> None:
        self.bus, self.adapter, self.handlers = bus, adapter, handlers
        self.tx = _TxCharacteristic()
        self.bridge = BleProtocolBridge(handlers, self.tx.notify)

    @classmethod
    async def create(cls, handlers: Handlers, adapter: str = "/org/bluez/hci0") -> "BluezPeripheral":
        return cls(await MessageBus(bus_type=BusType.SYSTEM).connect(), adapter, handlers)

    async def start(self) -> None:
        last4 = self.handlers.serial[-4:]
        self.bus.export(ROOT, _Application())
        self.bus.export(ROOT + "/service0", _Service())
        self.bus.export(ROOT + "/service0/char0", _RxCharacteristic(self.bridge.receive))
        self.bus.export(ROOT + "/service0/char1", self.tx)
        self.bus.export(ROOT + "/service0/char2", _InfoCharacteristic(self.handlers))
        self.bus.export(ROOT + "/advertisement0", _Advertisement(f"DGX Spark {last4}"))
        await self._call("org.bluez.GattManager1", "RegisterApplication", "oa{sv}", [ROOT, {}])
        await self._call("org.bluez.LEAdvertisingManager1", "RegisterAdvertisement", "oa{sv}", [ROOT + "/advertisement0", {}])
        asyncio.create_task(self._expiry_loop())

    async def _expiry_loop(self) -> None:
        while True:
            await asyncio.sleep(1)
            await self.bridge.expire()

    async def _call(self, interface: str, member: str, signature: str, body: list[Any]) -> None:
        reply = await self.bus.call(Message(destination=BLUEZ, path=self.adapter, interface=interface, member=member, signature=signature, body=body))
        if reply.message_type == MessageType.ERROR:
            raise RuntimeError(f"BlueZ {member} failed: {reply.error_name}: {reply.body}")


class _Application(ServiceInterface):
    def __init__(self) -> None:
        super().__init__("org.freedesktop.DBus.ObjectManager")

    @method()
    def GetManagedObjects(self) -> "a{oa{sa{sv}}}":
        return {}
