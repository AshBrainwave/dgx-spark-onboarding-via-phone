import argparse
import asyncio

from aiohttp import web

from sparkd_provision.api.handlers import Handlers
from sparkd_provision.net.mock_driver import MockDriver
from sparkd_provision.net.nm_driver import NetworkManagerDriver
from sparkd_provision.portal.server import create_app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--interface", help="NetworkManager-owned Wi-Fi interface for hardware mode")
    parser.add_argument("--host", help="HTTP bind address (default: localhost for mock, all addresses for hardware)")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    if args.mock:
        driver = MockDriver()
        host = args.host or "127.0.0.1"
    else:
        # This startup check intentionally fails before touching the interface when
        # NetworkManager does not own it; do not fight netplan or another manager.
        driver = asyncio.run(NetworkManagerDriver.create(args.interface))
        host = args.host or "0.0.0.0"
    web.run_app(create_app(Handlers(driver)), host=host, port=args.port)


if __name__ == "__main__":
    main()
