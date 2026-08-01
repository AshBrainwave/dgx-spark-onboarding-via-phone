import {
  b64url,
  createKeyPair,
  deriveSessionKey,
  encryptPsk,
  exportPublicKey,
} from "./crypto";
import type { Transport } from "../transport/types";

let count = 0;

export class ProtocolError extends Error {
  constructor(readonly code: string, message: string) {
    super(message);
  }
}

export class Client {
  sid: string | null = null;
  private sessionKey: CryptoKey | null = null;
  private counter = 0;

  constructor(private readonly transport: Transport) {}

  async call(op: string, body: Record<string, unknown> = {}) {
    const result = await this.transport.request({
      v: 1,
      id: `sim-${++count}`,
      op,
      sid: this.sid,
      body,
    });
    if (!result.ok) {
      throw new ProtocolError(result.err?.code ?? "UNKNOWN", result.err?.msg ?? "Request failed");
    }
    return result.body ?? {};
  }

  async open(qrDevicePublicKey: string) {
    const info = await this.call("device.info");
    if (info.pubkey !== qrDevicePublicKey) {
      throw new ProtocolError("PUBKEY_MISMATCH", "This isn't the Spark you scanned.");
    }
    const pair = await createKeyPair();
    const clientNonce = b64url(crypto.getRandomValues(new Uint8Array(16)));
    const body = await this.call("session.open", {
      client_pubkey: await exportPublicKey(pair.publicKey),
      nonce: clientNonce,
    });
    const devicePublicKey = String(body.device_pubkey);
    if (devicePublicKey !== qrDevicePublicKey) {
      throw new ProtocolError("PUBKEY_MISMATCH", "This isn't the Spark you scanned.");
    }
    this.sid = String(body.sid);
    this.sessionKey = await deriveSessionKey(pair.privateKey, devicePublicKey, clientNonce, String(body.nonce));
  }

  async connectWifi(ssid: string, security: string, password: string, hidden = false) {
    if (!this.sessionKey) {
      throw new ProtocolError("SESSION_EXPIRED", "No secure session is open.");
    }
    const pskEnc = await encryptPsk(this.sessionKey, ++this.counter, ssid, password);
    return this.call("wifi.connect", { ssid, security, psk_enc: pskEnc, hidden });
  }
}
