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
