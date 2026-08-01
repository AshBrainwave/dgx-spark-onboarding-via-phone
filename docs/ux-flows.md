# UX flows

The app is QR-first. Welcome opens a camera scanner (with a manual eight-character pairing
code and simulator path). Android with Web Bluetooth moves into the Bluetooth chooser;
iOS and browsers without BLE show the SoftAP name/password and a tappable `WIFI:` URI.

Choose Network shows RSSI bars, band, security, scan time, unsupported 802.1X entries, a
refresh control, and an Other network path. Password entry disables autocapitalization and
autocorrect, supports show/hide, and validates the WPA2 8–63 character range before send.
Applying always shows elapsed time and verbatim agent progress (`idle`, `scanning`,
`associating`, `authenticating`, `dhcp`, `verifying_internet`, `online`, `failed`).

If AP and STA cannot coexist, Reconnect explicitly tells the user to rejoin the home SSID
and displays a countdown. Success uses the LAN IP supplied by `wifi.status`, has a device
name field, copyable SSH command, and web-UI link. Every screen has a `?screen=<name>`
development route.

Errors return only to the relevant list, password, join, retry, or manual-IP action; they
never silently restart QR scanning. `PUBKEY_MISMATCH` is the only hard abort.

For review without hardware, use `?screen=error&error=<CODE>` for any listed protocol error,
for example `?screen=error&error=WIFI_AUTH_FAILED`. `SPARK_SIM_FAIL` accepts the same
uppercase code (and the documented short aliases) so each screen can also be reached through
the actual simulator flow. `WIFI_NO_INTERNET` deliberately continues to LAN-only success.
