"""Physical reset-button support for appliance images.

The Spark carrier board chooses the GPIO chip and line, so they are explicit service
arguments rather than guessed from a board revision.  A falling edge is a press on the
usual pull-up wiring.  The optional ``gpiod`` dependency is loaded only in hardware mode.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from datetime import timedelta


class ResetButtonError(RuntimeError):
    """Raised when configured physical-reset support cannot be started."""


class GpiodResetButton:
    """Watch an active-low GPIO button and invoke an asynchronous reset callback."""

    def __init__(self, request: object, on_press: Callable[[], Awaitable[None]]) -> None:
        self.request = request
        self.on_press = on_press
        self._task: asyncio.Task[None] | None = None
        self._last_press = 0.0

    @classmethod
    def create(
        cls, chip: str, line: int, on_press: Callable[[], Awaitable[None]]
    ) -> GpiodResetButton:
        try:
            import gpiod
            from gpiod.line import Bias, Direction, Edge
        except ImportError as exc:  # pragma: no cover - needs appliance package
            raise ResetButtonError(
                "physical reset was configured but gpiod is unavailable; install sparkd-provision[hardware]"
            ) from exc
        request = gpiod.request_lines(
            chip,
            consumer="sparkd-provision-reset",
            config={
                line: gpiod.LineSettings(
                    direction=Direction.INPUT,
                    edge_detection=Edge.FALLING,
                    bias=Bias.PULL_UP,
                )
            },
        )
        return cls(request, on_press)

    def start(self) -> None:
        self._task = asyncio.create_task(self._watch())

    async def close(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        # gpiod's request object owns the line and must be released on service stop.
        self.request.release()  # type: ignore[attr-defined]  # pragma: no cover - hardware only

    async def _watch(self) -> None:
        while True:
            # gpiod v2 blocks while waiting, so move that wait out of aiohttp's loop.
            pressed = await asyncio.to_thread(
                self.request.wait_edge_events, timedelta(seconds=1)  # type: ignore[attr-defined]
            )
            if not pressed:
                continue
            await asyncio.to_thread(self.request.read_edge_events)  # type: ignore[attr-defined]
            now = time.monotonic()
            if now - self._last_press >= 1:
                self._last_press = now
                await self.on_press()
