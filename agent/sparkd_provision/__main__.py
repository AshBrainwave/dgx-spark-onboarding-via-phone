import argparse
from pathlib import Path

from aiohttp import web

from sparkd_provision.api.handlers import Handlers
from sparkd_provision.net.mock_driver import MockDriver
from sparkd_provision.net.nm_driver import NetworkManagerDriver
from sparkd_provision.portal.server import create_app
from sparkd_provision.state import StateStore


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--interface", help="NetworkManager-owned Wi-Fi interface for hardware mode")
    parser.add_argument("--host", help="HTTP bind address (default: localhost for mock, all addresses for hardware)")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--state-path", type=Path, help="State file (default: /var/lib/sparkd-provision/state.json in hardware mode)")
    args = parser.parse_args()
    host = args.host or ("127.0.0.1" if args.mock else "0.0.0.0")
    state_path = args.state_path or (None if args.mock else Path("/var/lib/sparkd-provision/state.json"))
    state = StateStore(state_path)

    async def runtime_app() -> web.Application:
        if args.mock:
            driver = MockDriver()
        else:
            # This check intentionally happens before touching the interface when
            # NetworkManager does not own it; do not fight netplan or another manager.
            driver = await NetworkManagerDriver.create(args.interface)
            await driver.softap_up(state.state.ap_ssid, state.state.ap_psk)
        return create_app(Handlers(driver, state))

    web.run_app(runtime_app(), host=host, port=args.port)


if __name__ == "__main__":
    main()
