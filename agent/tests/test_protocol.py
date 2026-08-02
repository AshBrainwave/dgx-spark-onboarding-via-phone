import asyncio
import json
import random
import re
import struct
import time
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from dbus_fast import Variant

from sparkd_provision.api.handlers import Handlers
from sparkd_provision.ble_peripheral import BleProtocolBridge, _decode, _encode
from sparkd_provision.config import DeviceIdentity
from sparkd_provision.net import mock_driver
from sparkd_provision.net.capabilities import supports_concurrent_ap_sta
from sparkd_provision.net.driver import LinkStatus
from sparkd_provision.net.mock_driver import MockDriver
from sparkd_provision.net.nm_driver import (
    NetworkManagerDriver,
    _channel,
    _deduplicate_networks,
    _network_from_properties,
    _ssid_variant,
    _unbox,
)
from sparkd_provision.portal.dns import answer_a_query
from sparkd_provision.portal.server import _is_bound_host, _portal_html
from sparkd_provision.protocol.crypto import (
    b64url,
    decrypt_psk,
    derive_key,
    encrypt_psk,
    generate_keypair,
    unb64url,
)
from sparkd_provision.protocol.framing import Reassembler, fragment
from sparkd_provision.state import StateStore


async def test_mock_driver_accepts_every_documented_wifi_failure(monkeypatch) -> None:
    real_sleep = asyncio.sleep

    async def no_delay(_: float) -> None:
        await real_sleep(0)

    monkeypatch.setattr(mock_driver.asyncio, "sleep", no_delay)
    codes = (
        "WIFI_AUTH_FAILED",
        "WIFI_SSID_NOT_FOUND",
        "WIFI_WEAK_SIGNAL",
        "WIFI_DHCP_FAILED",
        "WIFI_NO_INTERNET",
        "WIFI_CAPTIVE_PORTAL",
        "WIFI_ENTERPRISE_UNSUPPORTED",
        "WIFI_BAND_MISMATCH",
        "DEVICE_LOST_AFTER_HANDOFF",
    )
    for code in codes:
        monkeypatch.setenv("SPARK_SIM_FAIL", code)
        driver = MockDriver()
        await driver.connect("Home", "password", "wpa2-psk")
        for _ in range(6):
            await real_sleep(0)
        assert (await driver.status()).err == code
    monkeypatch.delenv("SPARK_SIM_FAIL", raising=False)


def test_framing_round_trip() -> None:
    payload = b"x" * 101
    reassembler = Reassembler()
    completed = None
    for frame in fragment(payload, 42):
        completed = reassembler.add(frame) or completed
    assert completed == (42, payload)


def test_x25519_and_aes_gcm_round_trip() -> None:
    client_private, client_public = generate_keypair()
    device_private, device_public = generate_keypair()
    client_nonce = b64url(b"c" * 16)
    device_nonce = b64url(b"d" * 16)
    client_key = derive_key(client_private, device_public, client_nonce, device_nonce)
    device_key = derive_key(device_private, client_public, client_nonce, device_nonce)
    assert client_key == device_key
    assert (
        decrypt_psk(device_key, "Home", encrypt_psk(client_key, 1, "Home", "not-a-real-password"))
        == "not-a-real-password"
    )


async def test_handler_decrypts_ciphertext_without_password_on_wire() -> None:
    handlers = Handlers(MockDriver())
    client_private, client_public = generate_keypair()
    client_nonce = b64url(b"c" * 16)
    opened = await handlers.handle(
        {
            "v": 1,
            "id": "open",
            "op": "session.open",
            "sid": None,
            "body": {"client_pubkey": client_public, "nonce": client_nonce},
        }
    )
    session = opened["body"]
    key = derive_key(client_private, session["device_pubkey"], client_nonce, session["nonce"])
    password = "secret123"
    request = {
        "v": 1,
        "id": "connect",
        "op": "wifi.connect",
        "sid": session["sid"],
        "body": {
            "ssid": "Malegaonkar-5G",
            "security": "wpa2-psk",
            "psk_enc": encrypt_psk(key, 1, "Malegaonkar-5G", password),
            "hidden": False,
        },
    }
    assert password not in json.dumps(request)
    accepted = await handlers.handle(request)
    assert accepted["ok"] is True


async def test_tampered_ciphertext_returns_protocol_error() -> None:
    handlers = Handlers(MockDriver())
    _, client_public = generate_keypair()
    opened = await handlers.handle(
        {
            "v": 1,
            "id": "open",
            "op": "session.open",
            "sid": None,
            "body": {"client_pubkey": client_public, "nonce": b64url(b"n" * 16)},
        }
    )
    response = await handlers.handle(
        {
            "v": 1,
            "id": "tampered",
            "op": "wifi.connect",
            "sid": opened["body"]["sid"],
            "body": {"ssid": "Home", "security": "wpa2-psk", "psk_enc": b64url(b"x" * 40)},
        }
    )
    assert response["ok"] is False
    assert response["err"]["code"] == "INVALID_CIPHERTEXT"


def test_framing_fuzzes_sizes_order_and_drops() -> None:
    randomizer = random.Random(20260801)
    for _ in range(100):
        payload = randomizer.randbytes(randomizer.randrange(0, 1024))
        frames = fragment(payload, randomizer.randrange(1, 65535))
        shuffled = frames[:]
        randomizer.shuffle(shuffled)
        reassembler = Reassembler()
        completed = None
        for frame in shuffled:
            completed = reassembler.add(frame) or completed
        assert completed is not None
        assert completed[1] == payload
        if len(frames) > 1:
            reassembler = Reassembler()
            for frame in frames[:-1]:
                assert reassembler.add(frame) is None


def test_framing_expiry_reports_message_id() -> None:
    reassembler = Reassembler()
    reassembler.add(fragment(b"x" * 17, 77)[0])
    assert reassembler.expire(time.monotonic() + 11) == [77]


async def test_ble_bridge_decodes_handles_and_frames_response() -> None:
    sent: list[bytes] = []

    async def send(frame: bytes) -> None:
        sent.append(frame)

    bridge = BleProtocolBridge(Handlers(MockDriver()), send)
    request = {"v": 1, "id": "info", "op": "device.info", "sid": None, "body": {}}
    for frame in fragment(_encode(request), 9):
        await bridge.receive(frame)
    reassembler = Reassembler()
    response = None
    for frame in sent:
        response = reassembler.add(frame) or response
    assert response is not None
    assert _decode(response[1])["body"]["serial"] == "SIM-0001"


def test_shared_contract_fixtures_have_valid_envelopes() -> None:
    fixture_path = Path(__file__).parents[2] / "protocol" / "messages.json"
    for fixture in json.loads(fixture_path.read_text()):
        request = fixture["request"]
        assert request["v"] == 1
        assert isinstance(request["id"], str)
        assert isinstance(request["op"], str)
        assert isinstance(request["body"], dict)


def test_shared_crypto_vectors_match_protocol_ciphertext() -> None:
    vector_path = Path(__file__).parents[2] / "protocol" / "crypto-vectors.json"
    for vector in json.loads(vector_path.read_text()):
        private = X25519PrivateKey.from_private_bytes(unb64url(vector["client_private"]))
        key = derive_key(
            private, vector["device_public"], vector["client_nonce"], vector["device_nonce"]
        )
        assert (
            encrypt_psk(key, vector["counter"], vector["ssid"], vector["psk"])
            == vector["ciphertext"]
        )


def test_hardware_installer_uses_detected_interface_and_port_80() -> None:
    root = Path(__file__).parents[2]
    service = (root / "deploy/sparkd-provision.service").read_text()
    installer = (root / "scripts/first-boot.sh").read_text()

    assert "--interface ${SPARK_WIFI_INTERFACE} --port 80" in service
    assert "/opt/dgx-spark-onboarding/venv/bin/sparkd-provision" in service
    assert "wlan0" not in service
    assert "nmcli -t -f DEVICE,TYPE device status" in installer
    assert "agent[hardware]" in installer
    assert "dgx-spark-captive-dns.conf" in installer
    assert (root / "deploy/dgx-spark-captive-dns.conf").read_text().strip().endswith("port=0")


def test_real_networkmanager_scan_shapes_are_normalized() -> None:
    rows = [
        {
            "Ssid": b"Droid",
            "HwAddress": "0C:EF:15:D3:98:9C",
            "Frequency": 2437,
            "Strength": 70,
            "Flags": 0x3,
            "WpaFlags": 0,
            "RsnFlags": 0x588,
        },
        {
            "Ssid": b"Droid",
            "HwAddress": "0C:EF:15:D3:98:9D",
            "Frequency": 5240,
            "Strength": 57,
            "Flags": 0x3,
            "WpaFlags": 0,
            "RsnFlags": 0x588,
        },
        {
            "Ssid": b"Droid",
            "HwAddress": "2E:EF:15:D3:99:59",
            "Frequency": 6295,
            "Strength": 32,
            "Flags": 0x1,
            "WpaFlags": 0,
            "RsnFlags": 0x488,
        },
        {
            "Ssid": b"Enterprise",
            "HwAddress": "0E:FE:7B:42:E4:AE",
            "Frequency": 5785,
            "Strength": 24,
            "Flags": 0x1,
            "WpaFlags": 0,
            "RsnFlags": 0x288,
        },
        {
            "Ssid": b"",
            "HwAddress": "16:EF:15:D3:98:9C",
            "Frequency": 2437,
            "Strength": 69,
            "Flags": 0x1,
            "WpaFlags": 0,
            "RsnFlags": 0x188,
        },
    ]

    networks = _deduplicate_networks([_network_from_properties(row) for row in rows])
    droid = next(network for network in networks if network.ssid == "Droid")
    enterprise = next(network for network in networks if network.ssid == "Enterprise")
    hidden = next(network for network in networks if network.hidden)

    assert droid.bssid == "0C:EF:15:D3:98:9C"
    assert droid.rssi == -65
    assert droid.security == "wpa3-sae"
    assert droid.bands == ["2.4ghz", "5ghz", "6ghz"]
    assert enterprise.security == "wpa2-enterprise"
    assert enterprise.unsupported is True
    assert hidden.ssid == ""
    assert hidden.security == "wpa2-psk"
    assert _ssid_variant("Droid").value == b"Droid"


def test_hardware_identity_drives_radio_and_handoff_names(tmp_path) -> None:
    identity = DeviceIdentity(serial="spark-0268", model="NVIDIA DGX Spark")
    state = StateStore(tmp_path / "state.json", ap_ssid=f"DGX-Spark-{identity.last4}")
    handlers = Handlers(MockDriver(), state, serial=identity.serial, model=identity.model)

    assert identity.last4 == "0268"
    assert state.state.ap_ssid == "DGX-Spark-0268"
    assert handlers.serial == "spark-0268"
    assert handlers.hostname == "dgx-spark-0268"
    state.reset()
    assert state.state.ap_ssid == "DGX-Spark-0268"


async def test_concurrent_softap_uses_a_separate_networkmanager_device() -> None:
    driver = NetworkManagerDriver(None, "/device/sta", "wlP9s9")
    driver._concurrent_ap_sta = True
    device_lookups = 0
    activated = False
    iw_calls: list[tuple[str, ...]] = []
    dbus_calls: list[tuple[str, list[object]]] = []

    async def device_path(interface: str) -> str | None:
        nonlocal device_lookups
        assert interface == "wlP9s9-ap"
        device_lookups += 1
        return "/device/ap" if device_lookups > 1 else None

    async def run_iw(*arguments: str) -> None:
        iw_calls.append(arguments)

    async def device_property(path: str, interface: str, name: str) -> object:
        if (path, interface, name) == (
            "/device/ap",
            "org.freedesktop.NetworkManager.Device",
            "State",
        ):
            return 100 if activated else 30
        values = {
            ("/device/ap", "org.freedesktop.NetworkManager.Device", "Ip4Config"): "/ip4/ap",
            (
                "/device/sta",
                "org.freedesktop.NetworkManager.Device.Wireless",
                "ActiveAccessPoint",
            ): "/access-point/current",
            (
                "/access-point/current",
                "org.freedesktop.NetworkManager.AccessPoint",
                "Frequency",
            ): 2422,
        }
        return values[(path, interface, name)]

    async def call(
        path: str,
        interface: str,
        member: str,
        signature: str = "",
        body: list[object] | None = None,
    ) -> object:
        nonlocal activated
        del path, interface, signature
        values = body or []
        dbus_calls.append((member, values))
        if member == "AddConnectionUnsaved":
            settings = values[0]
            assert settings["connection"]["interface-name"].value == "wlP9s9-ap"
            assert settings["802-11-wireless"]["ssid"].value == b"DGX-Spark-3847"
            assert settings["802-11-wireless"]["band"].value == "bg"
            assert settings["802-11-wireless"]["channel"].value == 3
            return "/profile/ap"
        if member == "ActivateConnection":
            assert values == ["/profile/ap", "/device/ap", "/"]
            activated = True
            return "/active/ap"
        return None

    driver._device_path = device_path
    driver._property = device_property
    driver._run_iw = run_iw
    driver._call = call

    async def ipv4_details(_: str) -> tuple[str, str, str]:
        return "10.42.0.1", "", ""

    driver._ipv4_details = ipv4_details

    assert await driver.softap_up("DGX-Spark-3847", "SafePass2345") == "10.42.0.1"
    await driver.softap_down()

    assert ("dev", "wlP9s9", "interface", "add", "wlP9s9-ap", "type", "__ap") in iw_calls
    assert ("dev", "wlP9s9-ap", "del") in iw_calls
    assert [member for member, _ in dbus_calls] == [
        "AddConnectionUnsaved",
        "ActivateConnection",
        "DeactivateConnection",
        "Delete",
    ]
    assert [_channel(frequency) for frequency in (2412, 2422, 2484, 5180, 6295)] == [
        1,
        3,
        14,
        36,
        69,
    ]


def test_captive_dns_answers_any_a_query_with_ap_address() -> None:
    query = (
        struct.pack("!HHHHHH", 123, 0x0100, 1, 0, 0, 0)
        + b"\x07example\x03com\x00"
        + struct.pack("!HH", 1, 1)
    )
    response = answer_a_query(query, b"\xc0\x00\x02\x01")
    assert response is not None
    assert response[-4:] == b"\xc0\x00\x02\x01"


def test_captive_catch_all_accepts_default_port_host() -> None:
    assert _is_bound_host("10.42.0.1", "10.42.0.1", 80)
    assert _is_bound_host("10.42.0.1:80", "10.42.0.1", 80)
    assert not _is_bound_host("captive.apple.com", "10.42.0.1", 80)


def test_embedded_portal_is_self_contained() -> None:
    html = _portal_html()
    assert '<div id="root"></div>' in html
    assert '<script type="module">' in html
    assert "http://127.0.0.1:8080" not in html
    markup = re.sub(r"<(?:script|style)\b[\s\S]*?</(?:script|style)>", "", html)
    assert not re.search(r'\b(?:src|href)=["\'](?:https?:|/|\./assets/)', markup)


def test_networkmanager_nested_variants_are_unboxed() -> None:
    value = Variant(
        "aa{sv}",
        [{"address": Variant("s", "10.42.0.1"), "prefix": Variant("u", 24)}],
    )
    assert _unbox(value) == [{"address": "10.42.0.1", "prefix": 24}]


def test_wiphy_concurrent_ap_sta_parser_requires_two_interfaces() -> None:
    assert supports_concurrent_ap_sta("""
valid interface combinations:
 * #{ managed } <= 1, #{ AP } <= 1, total <= 2, #channels <= 1
""")
    assert not supports_concurrent_ap_sta("""
valid interface combinations:
 * #{ managed, AP } <= 1, total <= 1, #channels <= 1
""")


async def test_non_concurrent_connect_sends_handoff_before_dropping_ap(monkeypatch) -> None:
    monkeypatch.setenv("SPARK_SIM_CONCURRENT_AP_STA", "0")
    driver = MockDriver()
    handlers = Handlers(driver)
    _, public = generate_keypair()
    opened = await handlers.handle(
        {
            "v": 1,
            "id": "open",
            "op": "session.open",
            "sid": None,
            "body": {"client_pubkey": public, "nonce": b64url(b"n" * 16)},
        }
    )
    # Invalid cipher material is not the subject of this handoff test; use the
    # session key directly to produce an otherwise real connect envelope.
    encrypted = encrypt_psk(handlers.session_key, 1, "Home", "password")
    result = await handlers.handle(
        {
            "v": 1,
            "id": "connect",
            "op": "wifi.connect",
            "sid": opened["body"]["sid"],
            "body": {"ssid": "Home", "psk_enc": encrypted},
        }
    )
    assert result["body"]["handoff"]["mdns_name"] == "dgx-spark-0001.local"
    assert result["body"]["handoff"]["claim_token"]
    assert driver.ap_down_calls == 1


async def test_factory_reset_reopens_window_rotates_ap_and_restores_recovery_ap(tmp_path) -> None:
    state_path = tmp_path / "state.json"
    state = StateStore(state_path)
    old_password = state.state.ap_psk
    state.claim("old-owner")
    driver = MockDriver()
    handlers = Handlers(driver, state)

    await handlers.factory_reset()

    assert state.provisioning_open
    assert state.state.claimed is False
    assert state.state.owner_token_hash is None
    assert state.state.ap_psk != old_password
    assert driver.ap_up_calls == 1
    assert state_path.stat().st_mode & 0o777 == 0o600


async def test_existing_management_wifi_does_not_flip_captive_probes_online() -> None:
    driver = MockDriver()
    driver._status = LinkStatus(phase="online", ssid="management", ip="192.168.68.87")
    handlers = Handlers(driver)

    assert await handlers.provisioning_online() is False
    handlers._connect_requested = True
    assert await handlers.provisioning_online() is True
