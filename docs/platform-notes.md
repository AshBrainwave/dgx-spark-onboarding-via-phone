# Platform notes

- iOS browsers cannot use Web Bluetooth; SoftAP is the complete primary path.
- Web Bluetooth must be invoked by a user gesture; Android can also require Location Services.
- The system Bluetooth chooser is browser chrome and cannot be styled.
- iOS captive-network assistant is not Safari: no reliable storage, camera, service worker,
  or cookie persistence. QR scanning must happen first in the browser.
- Portal HTTP is intentional: a local AP cannot obtain publicly trusted TLS. PSK protection
  therefore depends on application-level encryption.
