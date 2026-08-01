# UX flows

The app is QR-first. Android uses Web Bluetooth when available; iOS and unsupported browsers
show SoftAP join instructions. Network selection comes from device scan results, passwords
are entered once, and the applying screen renders real status phases instead of a spinner.
The non-concurrent handoff path shows an explicit reconnection countdown.
