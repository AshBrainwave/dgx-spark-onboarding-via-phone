# Wire protocol

All messages use version `1` and a client-generated request id:

```json
{"v":1,"id":"01H...","op":"wifi.scan","sid":null,"body":{"force":false}}
```

Responses retain `v` and `id`, and contain either `ok: true` and `body` or `ok: false` and
`err`. The type definitions in `app/src/protocol/messages.ts` and
`agent/sparkd_provision/protocol/messages.py` are the generated-source equivalents for this
PoC; shared examples live in `protocol/messages.json`.

BLE uses 7-byte little-endian headers and 16-byte payload chunks. The fixed randomly chosen
GATT base UUID is `a66a068e-b4b7-4df6-a00d-7e2c04a36f26`.

Each BLE frame is `u8 ver=1, u8 flags (bit 0 final), u16 msg_id, u16 seq, u8 reserved`, then
at most 16 payload bytes (Web Bluetooth's default ATT MTU is 23). The payload is a gzip
compressed, base64url JSON envelope. Reassembly has a ten-second deadline and drops/NAKs
incomplete messages. CTRL_RX is write-without-response, CTRL_TX is notify, and INFO is a
read-only unencrypted device-info snapshot. The base UUID must be in the advertisement
service-UUID list; it is not sufficient to expose it after connect.

The browser suite includes a radio-free `LoopbackTransport` that fragments and reassembles
real request envelopes. It is the required first framing validation before Android hardware.

## GATT UUIDs

The one random 128-bit service UUID is `a66a068e-b4b7-4df6-a00d-7e2c04a36f26`.
`CTRL_RX` is `a66a068f-b4b7-4df6-a00d-7e2c04a36f26` (write without response), `CTRL_TX` is
`a66a0690-b4b7-4df6-a00d-7e2c04a36f26` (notify), and `INFO` is
`a66a0691-b4b7-4df6-a00d-7e2c04a36f26` (read-only, unencrypted). The peripheral must put
the service UUID in the advertising service-UUID list and advertise as `DGX Spark <last4>`.

Incomplete frames are dropped after ten seconds. The receiver should NAK the message ID;
the browser request also times out at ten seconds so it never hangs indefinitely.

On Linux, `sparkd_provision.ble_peripheral.BluezPeripheral` exports this exact profile via
BlueZ system D-Bus.  `CTRL_RX` schedules protocol handling after write-without-response,
`CTRL_TX` publishes every response frame as a notifying `Value`, and `INFO` returns the
unencrypted serial/public-key snapshot.  The `LEAdvertisement1.ServiceUUIDs` property
contains the base UUID and its `LocalName` is `DGX Spark <last4>`; both are essential for
Chrome's service-filtered chooser.  Its radio-free bridge test verifies the actual
gzip/base64url envelope and frame reassembly before hardware validation.
