"""Avahi publisher for a provisioned DGX Spark."""

from __future__ import annotations

from dbus_fast import BusType, Message, MessageType
from dbus_fast.aio import MessageBus

AVAHI_BUS = "org.freedesktop.Avahi"
AVAHI_SERVER = "org.freedesktop.Avahi.Server"
AVAHI_GROUP = "org.freedesktop.Avahi.EntryGroup"


class MdnsPublisher:
    def __init__(self, bus: MessageBus) -> None:
        self.bus = bus
        self.published = False

    @classmethod
    async def create(cls) -> MdnsPublisher:
        return cls(await MessageBus(bus_type=BusType.SYSTEM).connect())

    async def publish(
        self, name: str, hostname: str, address: str, port: int = 80
    ) -> None:
        if self.published:
            return
        group = await self._call("/", AVAHI_SERVER, "EntryGroupNew")
        await self._call(
            group,
            AVAHI_GROUP,
            "AddAddress",
            "iiuss",
            [-1, -1, 0, hostname, address],
        )
        await self._call(
            group,
            AVAHI_GROUP,
            "AddService",
            "iiussssqaay",
            [-1, -1, 0, name, "_dgx-spark._tcp", "local", hostname, port, []],
        )
        await self._call(group, AVAHI_GROUP, "Commit")
        self.published = True

    async def _call(self, path: str, interface: str, member: str, signature: str = "", body: list | None = None):
        reply = await self.bus.call(
            Message(destination=AVAHI_BUS, path=path, interface=interface, member=member, signature=signature, body=body or [])
        )
        if reply.message_type == MessageType.ERROR:
            raise RuntimeError(f"Avahi {member} failed: {reply.error_name}: {reply.body}")
        return reply.body[0] if reply.body else None
