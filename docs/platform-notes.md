# Platform notes

- iOS browsers cannot use Web Bluetooth; SoftAP is the complete primary path.
- Web Bluetooth must be invoked by a user gesture; Android can also require Location Services.
- The system Bluetooth chooser is browser chrome and cannot be styled.
- iOS captive-network assistant is not Safari: no reliable storage, camera, service worker,
  or cookie persistence. QR scanning must happen first in the browser.
- Portal HTTP is intentional: a local AP cannot obtain publicly trusted TLS. PSK protection
  therefore depends on application-level encryption.
- `requestDevice()` must be directly called from the Scan button’s user gesture. Explain
  the browser-owned chooser and the expected `DGX Spark <last4>` name before opening it.
- Declare the provisioning service in Web Bluetooth `filters`/`optionalServices`; a service
  absent from advertisements cannot be selected. Detect Android Location Services scan
  failures, reconnect once on `gattserverdisconnected`, and warn developers that Chrome may
  cache a restarted GATT table.

## NetworkManager ownership

Hardware mode uses NetworkManager's system D-Bus API through `dbus-fast`, never parsed
`nmcli` output. At startup it selects a Wi-Fi device (or the interface given with
`--interface`) and fails with an actionable error if NetworkManager does not own it. This is
intentional: provisioning must not race netplan or another network manager for the radio.

The SoftAP profile uses NetworkManager AP mode, WPA2, a 2.4 GHz `bg` band, and
`ipv4.method=shared`; NetworkManager then supplies DHCP and NAT. Hardware validation is
required before claiming this profile works on a specific radio.

At startup hardware mode creates (or restores) the AP from persisted state. Its WPA2 password
is twelve characters from an alphabet excluding ambiguous `0/O` and `1/I/l`; it runs on the
2.4 GHz `bg` band with NetworkManager shared IPv4. State storage is mode `0600`.

After Wi-Fi is online, hardware mode attempts to publish `DGX Spark` as
`_dgx-spark._tcp.local` through Avahi, with hostname `dgx-spark-0001.local` and portal port
8080. An unavailable Avahi daemon does not invalidate a completed Wi-Fi join: direct LAN-IP
status remains available and the missing advertisement is a deployment fault to surface.
