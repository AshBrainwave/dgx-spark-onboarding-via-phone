import argparse

from aiohttp import web

from sparkd_provision.api.handlers import Handlers
from sparkd_provision.net.mock_driver import MockDriver
from sparkd_provision.portal.server import create_app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    if not args.mock:
        parser.error("only --mock is implemented in the simulator milestone")
    web.run_app(create_app(Handlers(MockDriver())), host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
