# DGX Spark Phone Onboarding — Build Specification (PoC)

**Repo:** https://github.com/AshBrainwave/dgx-spark-onboarding-via-phone
**Target:** Proof of concept, runnable end-to-end without DGX Spark hardware
**Audience:** autonomous coding agent (Codex). Build to this spec; do not redesign it.
**Owner:** Ashutosh Malegaonkar (NVIDIA)

---

## 0. What we are building, in one paragraph

An Alexa/Tesla-style device onboarding experience for the NVIDIA DGX Spark, driven from a
phone. A brand-new Spark comes out of the box with no network configuration. The owner
opens a web app on their phone, scans a QR code on the Spark's chassis, and the app walks
them through handing the Spark their home Wi-Fi credentials. Ninety seconds later the Spark
is on their LAN and visible in the app. There are **two transports** to get credentials from
the phone into the Spark, chosen automatically by platform, and they carry the **same
application protocol**.

---

## 1. The constraint that drives the entire design

**iOS Safari does not implement Web Bluetooth, and never has.** Chrome and Firefox on iOS
are WebKit skins, so they do not have it either. A web app on iPhone therefore *cannot*
discover a Spark over BLE. This is why the Alexa and Tesla apps are native.

We are building a web app, so:

| Platform | Transport | Why |
|---|---|---|
| Android (Chrome/Edge 56+) | **Web Bluetooth GATT** | Supported; gives the in-app "device found" moment |
| iOS (any browser) | **SoftAP + captive portal** | Only option without a native app |
| Desktop Chrome (dev) | Either | For development convenience |

**Design rule that follows from this:** the SoftAP path is the *primary* path and must be
complete on its own. The BLE path is an *accelerator* for Android. Do not build features
into the BLE path that the SoftAP path cannot do — otherwise we ship two different products
and iOS users get the worse one.

### 1.1 Second constraint the product owner should know

A web app **cannot read the phone's current Wi-Fi SSID or password** on either platform.
There is no browser API for it, by design. So the "just push my current Wi-Fi settings to
the new device" behaviour that Alexa has (which uses iOS's `NEHotspotConfiguration` /
Android's `WifiManager` from *native* code, plus iCloud Keychain Wi-Fi sharing) is **not
achievable here**. The user will have to type their Wi-Fi password once.

Mitigations we *will* build (see §9): the Spark scans and returns the network list sorted by
signal strength so the user picks rather than types the SSID; we remember the SSID per owner
account for subsequent devices; and we validate the password against the real AP before
declaring success so a typo is caught in seconds, not after a reboot.

---

## 2. System components

```
┌─────────────────────────┐         ┌──────────────────────────────────────┐
│  Phone browser (PWA)    │         │  DGX Spark                           │
│                         │         │                                      │
│  app/  React+TS+Vite    │         │  agent/  sparkd-provision (Python)   │
│                         │         │                                      │
│  ┌───────────────────┐  │  BLE    │  ┌────────────────────────────────┐  │
│  │ transport/ble.ts  │──┼─────────┼─▶│ ble/gatt_server.py  (BlueZ)    │  │
│  ├───────────────────┤  │  GATT   │  ├────────────────────────────────┤  │
│  │ transport/http.ts │──┼─────────┼─▶│ portal/server.py    (aiohttp)  │  │
│  └───────────────────┘  │ SoftAP  │  └────────────────────────────────┘  │
│           │             │  HTTP   │                 │                    │
│  ┌────────▼──────────┐  │         │       ┌─────────▼──────────┐         │
│  │ protocol/  (one   │  │         │       │ api/handlers.py    │         │
│  │ JSON API, two     │  │         │       │ (one impl, two     │         │
│  │ pipes)            │  │         │       │  pipes)            │         │
│  └───────────────────┘  │         │       └─────────┬──────────┘         │
└─────────────────────────┘         │       ┌─────────▼──────────┐         │
                                    │       │ net/nm_driver.py   │         │
                                    │       │ net/mock_driver.py │         │
                                    │       └────────────────────┘         │
                                    └──────────────────────────────────────┘
```

**Non-negotiable architectural move:** `api/handlers.py` and `protocol/` know nothing about
BLE or HTTP. One request/response JSON protocol, two dumb pipes. If you find yourself
writing transport-specific business logic, stop and refactor.

---

## 3. Repository layout

Create exactly this structure.

```
dgx-spark-onboarding-via-phone/
├── README.md                       # quickstart: how to run the sim in 3 commands
├── STATUS.md                       # ← YOU maintain this, see §14
├── LICENSE                         # Apache-2.0
├── .github/workflows/ci.yml        # lint + typecheck + unit tests, both halves
├── docs/
│   ├── SPEC.md                     # this document, committed verbatim
│   ├── protocol.md                 # wire format, generated from the TS/py types
│   ├── security.md                 # threat model + key exchange
│   ├── state-machines.md           # device + app state diagrams (mermaid)
│   ├── ux-flows.md                 # screen-by-screen, both platforms
│   └── platform-notes.md           # captive portal quirks, Web BLE quirks (§10)
├── app/                            # phone-facing PWA
│   ├── package.json
│   ├── vite.config.ts              # two build targets: `hosted` and `portal`
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── transport/
│       │   ├── types.ts            # interface Transport { request(msg): Promise<msg> }
│       │   ├── ble.ts              # Web Bluetooth impl
│       │   ├── http.ts             # fetch impl against captive portal origin
│       │   └── select.ts           # platform detection + transport choice
│       ├── protocol/
│       │   ├── messages.ts         # zod schemas for every request/response
│       │   ├── framing.ts          # chunking/reassembly for BLE
│       │   ├── crypto.ts           # X25519 + HKDF + AES-GCM (WebCrypto)
│       │   └── client.ts           # typed API client over a Transport
│       ├── state/
│       │   └── machine.ts          # XState or hand-rolled FSM, see §7
│       ├── screens/                # see §8
│       └── components/
├── agent/                          # runs on the Spark
│   ├── pyproject.toml              # python >=3.11
│   ├── sparkd_provision/
│   │   ├── __main__.py
│   │   ├── config.py
│   │   ├── state.py                # device state machine, persisted
│   │   ├── api/handlers.py         # transport-agnostic
│   │   ├── protocol/{messages.py, framing.py, crypto.py}
│   │   ├── ble/gatt_server.py      # BlueZ D-Bus peripheral
│   │   ├── softap/manager.py       # bring AP up/down
│   │   ├── portal/server.py        # aiohttp + captive portal probe responders
│   │   ├── net/
│   │   │   ├── driver.py           # ABC: scan(), connect(), status(), teardown()
│   │   │   ├── nm_driver.py        # NetworkManager over D-Bus (real Spark)
│   │   │   └── mock_driver.py      # fake networks, scriptable failures
│   │   ├── qr.py                   # generate the enrollment QR payload + PNG
│   │   └── mdns.py                 # advertise _dgx-spark._tcp after provisioning
│   ├── systemd/sparkd-provision.service
│   └── tests/
├── sim/
│   └── run_sim.sh                  # agent in mock mode + app dev server, one command
└── scripts/
    ├── dev.sh
    └── flash-qr.sh                 # print an enrollment QR for a simulated device
```

---

## 4. Application protocol (transport-agnostic)

JSON over both pipes. Version every message. All responses carry `ok: boolean`.

### 4.1 Envelope

```jsonc
// request
{ "v": 1, "id": "01H...", "op": "wifi.scan", "sid": "<session id|null>", "body": { } }
// response
{ "v": 1, "id": "01H...", "ok": true,  "body": { } }
{ "v": 1, "id": "01H...", "ok": false, "err": { "code": "WIFI_AUTH_FAILED", "msg": "...", "detail": {} } }
```

`id` is a client-generated ULID used to correlate responses (mandatory for BLE, where
responses arrive as notifications out of band).

### 4.2 Operations

| op | body (req) | body (resp) | notes |
|---|---|---|---|
| `device.info` | — | `{serial, model, fw, state, capabilities, pubkey}` | Unauthenticated. `capabilities` includes `concurrent_ap_sta: bool` — see §6.4 |
| `session.open` | `{client_pubkey, nonce}` | `{sid, device_pubkey, nonce}` | X25519 ECDH, see §5 |
| `wifi.scan` | `{force: bool}` | `{networks: [...], scanned_at}` | See §4.3 |
| `wifi.connect` | `{ssid, security, psk_enc, hidden, band_pref}` | `{accepted: true}` | `psk_enc` is AES-GCM ciphertext. Returns immediately; poll `wifi.status` |
| `wifi.status` | — | `{phase, ssid, ip, gw, dns, rssi, err}` | Poll every 1s. `phase` per §7.1 |
| `wifi.forget` | — | `{}` | Abandon the attempt, return to advertising |
| `device.claim` | `{owner_label}` | `{owner_token}` | Binds device to this session; single-use |
| `device.rename` | `{name}` | `{name}` | Requires `owner_token` |
| `device.factory_reset` | `{confirm: true}` | `{}` | Requires `owner_token` or physical button |

### 4.3 Network list entry

```jsonc
{
  "ssid": "Malegaonkar-5G",
  "bssid": "aa:bb:cc:dd:ee:ff",
  "rssi": -47,                      // dBm
  "bars": 4,                        // 0-4, precomputed so the UI doesn't guess
  "security": "wpa2-psk",           // open | wep | wpa2-psk | wpa3-sae | wpa2-enterprise
  "band": "5ghz",                   // 2.4ghz | 5ghz | 6ghz
  "hidden": false,
  "saved": false
}
```

Sort descending by `rssi`. Deduplicate by SSID keeping the strongest BSSID, but if the same
SSID appears on multiple bands, keep one entry and set `"bands": ["2.4ghz","5ghz"]`. Mark
`wpa2-enterprise` entries as `unsupported: true` with a reason string — the PoC does not do
802.1X, but it must say so clearly rather than failing mysteriously.

### 4.4 BLE framing

Web Bluetooth exposes **no MTU negotiation API**. Assume the default 23-byte ATT MTU and
chunk accordingly — this is the single most common source of "works on my Pixel, fails on a
Samsung" bugs.

Frame header, little-endian, 7 bytes, leaving **16 bytes of payload per write**:

```
u8  ver      = 1
u8  flags    bit0 = last-fragment
u16 msg_id   truncated ULID hash, correlates req/resp
u16 seq      0-based fragment index
u8  reserved = 0
... payload (≤16 bytes)
```

- Client → device: write-without-response to `CTRL_RX`, fragments in order.
- Device → client: notify on `CTRL_TX`, same framing.
- Reassemble on both ends. 10s reassembly timeout, then drop and NAK.
- Payload is the JSON envelope, **gzip-compressed then base64url**, because a 30-network
  scan result is multiple kilobytes and 16 bytes at a time is slow. Show real progress in
  the UI while it streams (see §9.3).

### 4.5 GATT profile

Generate one random 128-bit base UUID at implementation time and record it in
`docs/protocol.md`. Do not use a 16-bit UUID.

| Characteristic | Properties | Purpose |
|---|---|---|
| `CTRL_RX` | write-without-response | client → device frames |
| `CTRL_TX` | notify | device → client frames |
| `INFO` | read | unencrypted `device.info` snapshot, so the chooser can show a useful name |

The **advertisement packet must include the service UUID in its service-UUID list**, not
just the GATT table — Web Bluetooth `filters: [{services: [...]}]` matches on the
advertisement, and a device that only exposes the service after connection will never appear
in the chooser. Advertise local name `DGX Spark <last4-of-serial>`.

---

## 5. Security model

Write this up properly in `docs/security.md`. Summary:

**Threat:** the user's home Wi-Fi PSK must reach the Spark without being recoverable by
anyone in radio range. Both transports are hostile by default — BLE advertisements and
unpaired GATT traffic are trivially sniffable, and the SoftAP may be open or use a PSK
printed on a sticker that is not secret.

**Design:**

1. On first boot (and on factory reset) the Spark generates an X25519 keypair. The public
   key lives in `INFO` and in the QR payload.
2. The phone reads the device pubkey **from the QR code**, not from the wire. It compares it
   against what the device reports. Mismatch ⇒ hard abort with "this doesn't look like the
   device on your desk". This is what stops a MITM AP with the same SSID.
3. `session.open` performs ECDH → HKDF-SHA256(salt = client_nonce ‖ device_nonce, info =
   `"dgx-spark-prov-v1"`) → 32-byte AES-256-GCM key.
4. `psk_enc` = AES-256-GCM(key, nonce = 12-byte counter, aad = ssid). The PSK is **never**
   logged, never written to a status file, never echoed back in `wifi.status`.
5. Provisioning is only accepted while device state is `FACTORY` or `PROVISIONING`, and only
   within **15 minutes** of boot or factory reset. After that, advertising stops and a
   physical button press is required to re-open the window. This is the anti-drive-by
   control.
6. **Single-claimer lock:** the first `session.open` wins and further sessions are refused
   with `SESSION_BUSY` until it completes, errors, or times out (90s idle).
7. `device.claim` issues a 256-bit `owner_token`; the Spark stores its hash. Post-provision
   management ops require it.
8. Rate limit: 5 `wifi.connect` attempts per session, exponential backoff on repeated auth
   failures.

**Explicitly out of scope for the PoC** (document as such, do not silently skip): a hardware
root of trust / attestation of the device pubkey against an NVIDIA-signed cert chain, TLS on
the captive portal (see §10.2 for why this is genuinely hard), and cloud account binding.

---

## 6. Spark-side agent

### 6.1 Network driver abstraction

`net/driver.py` defines the ABC. **Everything else in the agent talks only to this ABC.**

```python
class NetDriver(ABC):
    async def scan(self, force: bool = False) -> list[Network]: ...
    async def connect(self, ssid: str, psk: str, security: Security,
                      hidden: bool = False) -> None: ...      # returns once accepted
    async def status(self) -> LinkStatus: ...
    async def forget(self) -> None: ...
    async def softap_up(self, ssid: str, psk: str) -> None: ...
    async def softap_down(self) -> None: ...
    @property
    def supports_concurrent_ap_sta(self) -> bool: ...
```

Two implementations:

- **`mock_driver.py`** — returns a fixed but realistic network list (mix of bands, one
  hidden, one enterprise, one open, RSSI from -35 to -89). Scriptable failure injection via
  env var `SPARK_SIM_FAIL=auth|dhcp|timeout|weak|captive|none` so every error screen in §11
  can be demoed without hardware. **This must work on a developer laptop with no Wi-Fi
  hardware access at all.**
- **`nm_driver.py`** — NetworkManager over D-Bus (`sdbus` or `dbus-fast`). Prefer the D-Bus
  API over shelling out to `nmcli`; parse-the-CLI is fragile. DGX OS is Ubuntu-based and
  ships NetworkManager for the Wi-Fi interface. **Detect at startup** whether NM owns the
  wireless device (`nmcli device status`) and if it does not, fail loudly with a clear
  message rather than fighting netplan for control of the interface.

### 6.2 SoftAP

Use NetworkManager AP mode (`802-11-wireless.mode=ap`, `ipv4.method=shared`) rather than
hand-rolling hostapd+dnsmasq — NM's `shared` mode gives DHCP and NAT for free and won't
fight NM for the interface. SSID `DGX-Spark-<last4>`, WPA2 PSK, 12 random chars from an
unambiguous alphabet (no `0/O`, `1/l/I`), regenerated on factory reset. Channel: pick a
2.4 GHz channel — **phones connect to 2.4 GHz AP more reliably and it has better range in
a room with the box sitting on a desk**; 5 GHz gains nothing here.

### 6.3 Captive portal

`portal/server.py` binds `0.0.0.0:80` on the AP interface and must respond to the OS probe
URLs so the phone auto-opens the portal:

| Platform | Probe | Expected "internet is fine" response | We return |
|---|---|---|---|
| iOS/macOS | `http://captive.apple.com/hotspot-detect.html` | body exactly `<HTML><HEAD><TITLE>Success</TITLE></HEAD><BODY>Success</BODY></HTML>` | `302` to `/portal/` |
| Android | `http://connectivitycheck.gstatic.com/generate_204` | HTTP `204` | `302` to `/portal/` |
| Windows | `http://www.msftconnecttest.com/connecttest.txt` | body `Microsoft Connect Test` | `302` to `/portal/` |

Catch-all: any `Host:` header that is not ours → 302 to the portal. Run a DNS responder on
port 53 answering every A query with the AP's own IP.

**After successful provisioning**, start answering the probes *correctly* (204 / Success) so
the phone stops nagging and dismisses the captive sheet cleanly.

### 6.4 The handoff problem — read this carefully

When the Spark leaves AP mode to join the home network, the phone's connection to it dies
mid-flow. This is the step every consumer device gets wrong and it is where our UX wins or
loses. Two cases:

**(a) Chipset supports concurrent AP+STA.** Keep the AP up while associating with the home
network. Report full success over the AP, show the user the Spark's new LAN IP, *then* tear
the AP down after they acknowledge. Clean, no dead air. Report
`capabilities.concurrent_ap_sta = true`.

**(b) Chipset does not.** Then:
1. Before dropping the AP, send the client everything it will need to find the Spark again:
   `{mdns_name, expected_hostname, claim_token}`.
2. Client shows an explicit "Reconnecting you to *<home SSID>*" screen with a countdown, not
   a spinner that silently dies.
3. Spark applies creds and joins. If it fails, it **must** bring the SoftAP back up within
   20s and set `wifi.status.phase = failed` with the error, so the returning phone learns
   why. A device that fails and stays dark is unrecoverable without a keyboard.
4. Client polls `http://<mdns_name>.local/api/v1/wifi/status`. mDNS `.local` resolves from
   iOS Safari (Bonjour) but is **unreliable from Android Chrome** — so also try a small
   candidate-IP sweep from the gateway's subnet and offer a manual "enter the IP shown on
   the Spark's display" fallback.

**Detect which case you're in at runtime** (query the wiphy's `valid_interface_combinations`
via `iw phy` or NL80211) and branch. Do not assume.

### 6.5 Device state machine

`FACTORY → ADVERTISING → CLAIMED → APPLYING → {ONLINE | FAILED} → PROVISIONED`
plus `FAILED → ADVERTISING` on retry, and `* → FACTORY` on reset. Persist to
`/var/lib/sparkd-provision/state.json` (mode 0600) so a reboot mid-flow resumes sanely.
Diagram it in `docs/state-machines.md`.

---

## 7. Phone app

React 18 + TypeScript + Vite. **No UI framework with a heavy runtime** — the captive portal
WebView is constrained (§10.2), so keep the portal bundle under 300 KB gzipped and free of
service workers, WebRTC, and dynamic `import()`.

Two Vite build targets:
- `hosted` — full PWA, deployed to GitHub Pages, used for the Android BLE path. **Must be
  HTTPS**: Web Bluetooth requires a secure context.
- `portal` — single self-contained bundle embedded in the agent, inlined CSS/JS, no external
  fetches of any kind (there is no internet on the SoftAP).

### 7.1 App state machine

```
idle
 └─▶ scan_qr ──▶ qr_parsed
        ├─(android + BLE available)─▶ ble_request_device ─▶ ble_connecting ─▶ secure_channel
        └─(ios | no BLE)───────────▶ show_join_ap ─▶ (user joins) ─▶ portal_loaded ─▶ secure_channel
secure_channel ─▶ wifi_list ─▶ creds_entry ─▶ applying
applying ─▶ (phase: associating → dhcp → verifying) ─▶ handoff? ─▶ verifying_from_lan ─▶ claimed ─▶ success
   └─▶ failed_<code>  ─▶ (back to wifi_list or creds_entry, NEVER back to scan_qr)
```

`wifi.status.phase` enum, surfaced verbatim to the user as progress copy:
`idle | scanning | associating | authenticating | dhcp | verifying_internet | online | failed`

### 7.2 Screens

Build these, in `app/src/screens/`. Each gets a Storybook-less but standalone dev route so
they can be reviewed without hardware.

1. **Welcome** — "Set up your DGX Spark". One primary button: *Scan the QR code*.
2. **QR scanner** — `BarcodeDetector` where available, `@zxing/browser` fallback. Manual
   entry link for the 8-char pairing code printed under the QR.
3. **Join AP (iOS)** — big instructions + a tappable `WIFI:` URI. Shows the AP name and
   password in large monospace so it can be typed if the tap fails.
4. **Connecting to Spark** — BLE or portal handshake, with a real substep list.
5. **Choose network** — the scan list. Signal bars, band chip, lock icon. Enterprise entries
   greyed with "Not supported yet". "Other network…" at the bottom for hidden SSIDs. A
   refresh affordance that shows *when* the list was scanned.
6. **Password** — show/hide toggle, `autocomplete="current-password"`, no autocapitalize, no
   autocorrect, `inputmode="text"`. Live length hint (WPA2 PSK is 8–63 chars) so a truncated
   paste is caught before submit.
7. **Applying** — see §9.3, the substep list, not a spinner.
8. **Reconnect** — only in the non-concurrent case (§6.4b). Countdown + explicit instruction.
9. **Success** — device name entry, the Spark's LAN IP and hostname, and a *next action*
   (see §9.5).
10. **Error screens** — one per code in §11, each with cause, fix, and a back affordance.

---

## 8. Platform quirks to handle explicitly

Document all of these in `docs/platform-notes.md` as you implement them.

### 8.1 Web Bluetooth (Android)
- Requires a **user gesture** to call `requestDevice()`. Cannot be triggered from a timer or
  a promise chain that lost gesture context.
- The device chooser is **browser chrome — you cannot style it or render your own list**.
  Design the copy around this: tell the user what they are about to see and what to pick.
- Every service you will access must be in `filters` or `optionalServices` at request time.
- Android may require Location Services enabled system-wide for BLE scanning; detect the
  failure and give a specific instruction rather than "connection failed".
- `gattserverdisconnected` fires often. Implement one automatic reconnect with the cached
  device before surfacing an error.
- Chrome on Android caches GATT services aggressively; if the agent restarts with a changed
  GATT table the client may see stale characteristics. Note it in the dev docs.

### 8.2 Captive portal WebView (iOS CNA)
- It is **not Safari**. No service workers, no `localStorage` persistence you can rely on,
  no camera access, separate cookie jar, and it can be dismissed by the OS at any time.
- Therefore: **the QR scan must happen before joining the AP**, in the real browser. The
  portal receives the session context via the URL the QR flow hands off, or the user
  re-enters the 8-char code. Do not design a flow that needs the camera inside the CNA.
- Provide a prominent "Open in Safari" escape hatch — some users and some iOS versions do
  better there, and Safari can use the camera.
- **TLS is impractical here**: there is no public DNS name for the AP and no CA will issue
  for a `.local`/IP. The portal runs plain HTTP; this is exactly why §5's application-layer
  encryption of the PSK is mandatory rather than optional.

### 8.3 General
- Test on: iOS Safari (current − 1), Android Chrome (current − 1), and desktop Chrome.
- Respect `prefers-reduced-motion` and `prefers-color-scheme`.

---

## 9. Where we beat the incumbent experience

This is the actual point of the project. Implement all of these; they are requirements, not
polish.

1. **QR-first, zero typing of identifiers.** The user never types an SSID, a device name, or
   a serial. One scan seeds the AP name, AP password, device pubkey, and pairing code.
2. **Never a bare spinner.** The Applying screen streams real substeps with elapsed time:
   `Sending credentials ✓ · Associating with Malegaonkar-5G ✓ · Getting an address… ✓
   192.168.1.44 · Checking internet…`. Users tolerate 60 seconds of *visible* progress and
   abandon at 15 seconds of a spinner.
3. **Failures name the cause and the fix.** Never "Setup failed". See §11.
4. **Resumable.** Losing the connection, backgrounding the app, or locking the phone must
   not restart the flow. Persist `{claim_token, device_id, step}` and resume on reopen.
5. **The success screen is not a dead end.** Show the LAN address, offer to open the Spark's
   web UI / copy an `ssh` command, and name the device. Alexa dumps you back to a device
   list; we should hand the user their next action.
6. **Honest pre-flight.** Before asking for the password, warn if the chosen network is
   enterprise (unsupported), if RSSI < −75 dBm ("weak signal where your Spark is sitting —
   consider moving it"), or if the network looks like a captive-portal hotel/campus network.
7. **A recovery path that does not need a keyboard.** If provisioning fails, the Spark
   re-advertises and the phone can retry. Document the physical-button reset in the README.

---

## 10. Error taxonomy

Every one of these is a distinct `err.code`, a distinct screen, and a distinct mock-driver
failure injection. This table *is* the test matrix.

| Code | Cause | User-facing message | Recovery |
|---|---|---|---|
| `WIFI_AUTH_FAILED` | Wrong PSK | "That password didn't work for *<ssid>*." | Back to password, prefilled SSID |
| `WIFI_SSID_NOT_FOUND` | Network gone / out of range | "Couldn't find *<ssid>* anymore." | Back to list, force rescan |
| `WIFI_WEAK_SIGNAL` | Associated but RSSI < −80 | "Signal is too weak where your Spark is." | Suggest moving, retry |
| `WIFI_DHCP_FAILED` | Associated, no lease | "Joined the network but couldn't get an address." | Retry; suggest router reboot |
| `WIFI_NO_INTERNET` | Lease but no route out | "On your network, but no internet." | Offer to continue anyway (LAN-only is valid for a Spark) |
| `WIFI_CAPTIVE_PORTAL` | Home net needs a browser login | "*<ssid>* needs a sign-in page. Spark can't do that." | Suggest a different network / MAC allowlist |
| `WIFI_ENTERPRISE_UNSUPPORTED` | 802.1X | "Enterprise Wi-Fi isn't supported yet." | Suggest Ethernet |
| `WIFI_BAND_MISMATCH` | 5 GHz-only SSID, radio on 2.4 | "Spark can't see the 5 GHz band from here." | Show 2.4 GHz twin if present |
| `SESSION_BUSY` | Another phone is claiming | "Someone else is setting up this Spark." | Wait / retry after 90s |
| `SESSION_EXPIRED` | 15-min window closed | "Setup window closed for safety." | Instruct: press the reset button |
| `PUBKEY_MISMATCH` | QR ≠ device key | "This isn't the Spark you scanned." | Hard abort, no retry |
| `BLE_DISCONNECTED` | GATT drop | (auto-retry once, then) "Lost Bluetooth connection." | Move closer, retry |
| `BLE_UNSUPPORTED` | iOS / old browser | (never shown — we route to SoftAP) | n/a |
| `PORTAL_UNREACHABLE` | Phone not on the AP | "You're not connected to *<ap ssid>* yet." | Re-show join instructions |
| `DEVICE_LOST_AFTER_HANDOFF` | Can't find it on LAN | "Spark joined but we can't reach it." | Manual IP entry, or SoftAP retry |

---

## 11. Simulator — build this first

`sim/run_sim.sh` must, with **no DGX Spark and no Wi-Fi hardware**:
1. Start the agent with `mock_driver`, HTTP transport on `localhost:8080`.
2. Start the Vite dev server for the app, configured to talk to it.
3. Print an enrollment QR (PNG + terminal ASCII) for the simulated device.
4. Honour `SPARK_SIM_FAIL=<code>` to force any error in §10.
5. Honour `SPARK_SIM_CONCURRENT_AP_STA=0|1` to exercise both handoff paths.

**A reviewer must be able to see the entire flow, including every error screen, on a laptop
in under 60 seconds from `git clone`.** Getting this right is worth more than any other
single item in this spec — build it before the BLE path, before the NM driver, before
anything real.

---

## 12. Testing

- **Unit:** framing/reassembly (fuzz with random fragment sizes and drops), crypto vectors,
  message schema round-trip TS↔Python, scan-list dedup/sort, every state transition.
- **Integration:** full flow against `mock_driver` via HTTP, and via a loopback BLE fake
  (a `Transport` impl that pipes frames in-process, so framing is exercised without radios).
- **Contract:** one shared `protocol/messages.json` fixture set that both the TS and Python
  test suites load, so the two implementations cannot drift.
- **Manual matrix** (document in `docs/`, run when hardware exists): iOS Safari + SoftAP;
  Android Chrome + BLE; Android Chrome + SoftAP fallback.

CI: lint + typecheck + unit + integration on every push. No hardware in CI.

---

## 13. Build order

Do it in this order and commit at each step.

1. Repo skeleton, README, CI, this spec in `docs/`.
2. Protocol types + framing + crypto, both languages, with contract tests. **No I/O yet.**
3. `mock_driver` + `api/handlers.py` + HTTP portal server.
4. App: transport abstraction, HTTP transport, state machine, all screens against the mock.
5. `sim/run_sim.sh` — the whole flow demoable on a laptop. **Milestone: tag `v0.1-sim`.**
6. All error screens + failure injection. **Milestone: `v0.2-errors`.**
7. BLE: GATT server (BlueZ) + `transport/ble.ts`. Test agent-on-Linux ↔ Android phone.
   **Milestone: `v0.3-ble`.**
8. `nm_driver` + SoftAP manager + captive portal probe responders + mDNS. Test on real
   Linux with a Wi-Fi adapter. **Milestone: `v0.4-hw`.**
9. Handoff logic, both concurrent and non-concurrent paths.
10. DGX Spark bring-up: systemd unit, first-boot integration, QR generation.

Steps 1–6 need no hardware at all. **Do not block on hardware availability** — if you hit
something that genuinely requires a Spark, note it in `STATUS.md` under *Blocked* and keep
going on the next item.

---

## 14. Your process — STATUS.md

Maintain `STATUS.md` at the repo root, committed, updated **after every meaningful unit of
work** (not just at the end). It is how progress is monitored. Exact format:

```markdown
# DGX Spark Onboarding — Build Status

**Overall:** in_progress | blocked | done
**Current step:** 4 — App screens against mock
**Updated:** 2026-07-31T18:04:11Z

## Milestones
- [x] 1. Repo skeleton + CI
- [x] 2. Protocol + framing + crypto (contract tests green)
- [ ] 3. Mock driver + HTTP portal        ← in progress
- [ ] 4. App screens
...

## Done since last update
- <one line per item, with the commit sha>

## Blocked
- <what, why, and exactly what you need from a human — or "nothing">

## Decisions I made that the spec didn't cover
- <anything you had to invent, so it can be reviewed>

## Next
- <the next 1-3 concrete actions>
```

Rules:
- Never leave `Blocked` stale. If you unblock yourself, move it to *Done*.
- If you deviate from this spec, log it under *Decisions* with a one-line rationale. Do not
  silently redesign.
- Commit frequently with meaningful messages. Small commits over big ones.

---

## 15. Repo setup

The GitHub repo **already exists and is public**:
`https://github.com/AshBrainwave/dgx-spark-onboarding-via-phone.git`

1. Clone it. If it is empty, initialise `main` with the skeleton from §3.
2. `git config user.name` / `user.email` are **not set on this machine** — set them to the
   owner's identity before the first commit.
3. **Push credentials are not present on this machine** (`gh` is not installed and there is
   no credential helper or token). Do all work and commit locally. If a push fails,
   record it in `STATUS.md` under *Blocked* with the exact command that failed, and
   **continue building** — do not stall waiting for credentials.

---

## 16. Open questions for the human (answer in STATUS.md, don't guess silently)

1. Is there a DGX Spark available to test against, or is this laptop/Linux-only for now?
   (Spec assumes no hardware; steps 1–6 are unaffected either way.)
2. Should the hosted build deploy to GitHub Pages, or is there an NVIDIA-internal host?
3. Is there an existing NVIDIA account/identity system the `device.claim` step should bind
   to, or is a local owner token fine for the PoC? (Spec assumes local token.)
4. Does the Spark chassis design have room for a QR sticker, and does the first-boot display
   output exist so we can show the pairing code on screen as a fallback?
