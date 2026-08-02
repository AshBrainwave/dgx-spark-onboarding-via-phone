import argparse
from pathlib import Path

from aiohttp import web

from sparkd_provision.api.handlers import Handlers
from sparkd_provision.ble_peripheral import BluezPeripheral
from sparkd_provision.config import DeviceIdentity
from sparkd_provision.net.mdns import MdnsPublisher
from sparkd_provision.net.mock_driver import MockDriver
from sparkd_provision.net.nm_driver import NetworkManagerDriver
from sparkd_provision.portal.dns import start_dns_responder
from sparkd_provision.portal.server import create_app
from sparkd_provision.reset_button import GpiodResetButton
from sparkd_provision.state import StateStore


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--interface", help="NetworkManager-owned Wi-Fi interface for hardware mode")
    parser.add_argument("--host", help="HTTP bind address (default: localhost for mock, all addresses for hardware)")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--bluetooth-adapter", default="/org/bluez/hci0")
    parser.add_argument("--no-ble", action="store_true", help="Do not export the BlueZ provisioning GATT service")
    parser.add_argument("--state-path", type=Path, help="State file (default: /var/lib/sparkd-provision/state.json in hardware mode)")
    parser.add_argument("--reset-gpio-chip", help="GPIO chip for the active-low physical reset button, for example /dev/gpiochip0")
    parser.add_argument("--reset-gpio-line", type=int, help="GPIO line offset for the physical reset button")
    args = parser.parse_args()
    host = args.host or ("127.0.0.1" if args.mock else "0.0.0.0")
    state_path = args.state_path or (None if args.mock else Path("/var/lib/sparkd-provision/state.json"))
    identity = DeviceIdentity.simulated() if args.mock else DeviceIdentity.hardware()
    state = StateStore(state_path, ap_ssid=f"DGX-Spark-{identity.last4}")
    if (args.reset_gpio_chip is None) != (args.reset_gpio_line is None):
        parser.error("--reset-gpio-chip and --reset-gpio-line must be provided together")

    async def runtime_app() -> web.Application:
        mdns = None
        driver = None
        dns_transport = None
        if args.mock:
            driver = MockDriver()
        else:
            # This check intentionally happens before touching the interface when
            # NetworkManager does not own it; do not fight netplan or another manager.
            driver = await NetworkManagerDriver.create(args.interface)
            ap_address = None
            if not state.state.claimed:
                ap_address = await driver.softap_up(
                    state.state.ap_ssid, state.state.ap_psk
                )
            try:
                mdns = await MdnsPublisher.create()
            except (OSError, RuntimeError):
                # Wi-Fi provisioning remains usable if Avahi is not installed; status
                # is still available through the AP and direct LAN IP.
                mdns = None
        try:
            handlers = Handlers(driver, state, mdns, serial=identity.serial, model=identity.model)
            app = create_app(handlers)
            if not args.mock and ap_address:
                dns_transport = await start_dns_responder(ap_address)
                app["dns_transport"] = dns_transport
            if args.reset_gpio_chip is not None:
                button = GpiodResetButton.create(
                    args.reset_gpio_chip, args.reset_gpio_line, handlers.factory_reset
                )
                button.start()
                app["reset_button"] = button

                async def close_reset(_: web.Application) -> None:
                    await button.close()

                app.on_cleanup.append(close_reset)
            if not args.mock and not args.no_ble:
                peripheral = await BluezPeripheral.create(handlers, args.bluetooth_adapter)
                await peripheral.start()
                # Keep the bus and exported D-Bus objects alive for aiohttp's life.
                app["ble_peripheral"] = peripheral
            if not args.mock:

                async def close_hardware(_: web.Application) -> None:
                    if dns_transport is not None:
                        dns_transport.close()
                    await driver.softap_down()

                app.on_cleanup.append(close_hardware)
            return app
        except BaseException:
            if dns_transport is not None:
                dns_transport.close()
            if not args.mock and driver is not None:
                await driver.softap_down()
            raise

    web.run_app(runtime_app(), host=host, port=args.port)


if __name__ == "__main__":
    main()
