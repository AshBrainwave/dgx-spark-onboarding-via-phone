import { fragment, Reassembler } from "../protocol/framing";
import type { RequestMessage, ResponseMessage, Transport } from "./types";

type GattCharacteristic = {
  value: DataView | null;
  writeValueWithoutResponse(value: ArrayBuffer): Promise<void>;
  startNotifications(): Promise<GattCharacteristic>;
  addEventListener(type: "characteristicvaluechanged", listener: (event: Event) => void): void;
};
type GattService = { getCharacteristic(uuid: string): Promise<GattCharacteristic> };
type GattServer = { getPrimaryService(uuid: string): Promise<GattService> };
type Gatt = { connect(): Promise<GattServer> };
type BleDevice = { gatt?: Gatt; addEventListener(type: "gattserverdisconnected", listener: () => void): void };
type BluetoothApi = { requestDevice(options: unknown): Promise<BleDevice> };
const bluetooth = () => (navigator as Navigator & { bluetooth?: BluetoothApi }).bluetooth;

export const SERVICE_UUID = "a66a068e-b4b7-4df6-a00d-7e2c04a36f26";
export const CTRL_RX_UUID = "a66a068f-b4b7-4df6-a00d-7e2c04a36f26";
export const CTRL_TX_UUID = "a66a0690-b4b7-4df6-a00d-7e2c04a36f26";
export const INFO_UUID = "a66a0691-b4b7-4df6-a00d-7e2c04a36f26";

export const shouldUseBle = () =>
  "bluetooth" in navigator && !/iPhone|iPad|iPod/i.test(navigator.userAgent);

async function gzip(bytes: Uint8Array): Promise<Uint8Array> {
  if (!("CompressionStream" in window)) {
    throw new Error("This browser cannot prepare Bluetooth messages. Use the Spark Wi-Fi portal.");
  }
  const copy = new Uint8Array(bytes).buffer as ArrayBuffer;
  const stream = new Blob([copy]).stream().pipeThrough(new CompressionStream("gzip"));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

async function gunzip(bytes: Uint8Array): Promise<Uint8Array> {
  if (!("DecompressionStream" in window)) {
    throw new Error("This browser cannot read Bluetooth messages. Use the Spark Wi-Fi portal.");
  }
  const copy = new Uint8Array(bytes).buffer as ArrayBuffer;
  const stream = new Blob([copy]).stream().pipeThrough(new DecompressionStream("gzip"));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

function b64url(bytes: Uint8Array): string {
  let text = "";
  for (const byte of bytes) text += String.fromCharCode(byte);
  return btoa(text).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", "");
}

function unb64url(text: string): Uint8Array {
  const padded = text.replaceAll("-", "+").replaceAll("_", "/").padEnd(Math.ceil(text.length / 4) * 4, "=");
  return Uint8Array.from(atob(padded), value => value.charCodeAt(0));
}

async function encode(message: RequestMessage): Promise<Uint8Array> {
  const compressed = await gzip(new TextEncoder().encode(JSON.stringify(message)));
  return new TextEncoder().encode(b64url(compressed));
}

async function decode(payload: Uint8Array): Promise<ResponseMessage> {
  const json = await gunzip(unb64url(new TextDecoder().decode(payload)));
  return JSON.parse(new TextDecoder().decode(json)) as ResponseMessage;
}

/** Web Bluetooth transport. Call chooseDevice only from a button/tap handler. */
export class BleTransport implements Transport {
  private device: BleDevice | null = null;
  private rx: GattCharacteristic | null = null;
  private readonly reassembler = new Reassembler();
  private readonly replies = new Map<number, (value: ResponseMessage) => void>();
  private sequence = 0;
  private reconnecting = false;

  async chooseDevice(): Promise<void> {
    // The filter is intentionally a service filter: Chrome matches it in advertisements.
    const api = bluetooth();
    if (!api) throw new Error("Web Bluetooth is not available");
    this.device = await api.requestDevice({
      filters: [{ services: [SERVICE_UUID] }],
      optionalServices: [SERVICE_UUID],
    });
    this.device.addEventListener("gattserverdisconnected", () => void this.reconnectOnce());
    await this.connect();
  }

  async request(message: RequestMessage): Promise<ResponseMessage> {
    if (!this.rx) throw new Error("Bluetooth is not connected");
    const messageId = ++this.sequence;
    const reply = new Promise<ResponseMessage>((resolve, reject) => {
      const timer = window.setTimeout(() => {
        this.replies.delete(messageId);
        reject(new Error("Spark did not reply over Bluetooth"));
      }, 10_000);
      this.replies.set(messageId, value => {
        window.clearTimeout(timer);
        resolve(value);
      });
    });
    for (const frame of fragment(await encode(message), messageId)) {
      await this.rx.writeValueWithoutResponse(new Uint8Array(frame).buffer as ArrayBuffer);
    }
    return reply;
  }

  private async connect(): Promise<void> {
    if (!this.device?.gatt) throw new Error("No Bluetooth GATT server is available");
    const server = await this.device.gatt.connect();
    const service = await server.getPrimaryService(SERVICE_UUID);
    this.rx = await service.getCharacteristic(CTRL_RX_UUID);
    const tx = await service.getCharacteristic(CTRL_TX_UUID);
    await tx.startNotifications();
    tx.addEventListener("characteristicvaluechanged", event => void this.onFrame(event));
  }

  private async onFrame(event: Event): Promise<void> {
    const value = (event.target as unknown as GattCharacteristic).value;
    if (!value) return;
    const complete = this.reassembler.add(new Uint8Array(value.buffer));
    if (!complete) return;
    const resolve = this.replies.get(complete.messageId);
    if (!resolve) return;
    this.replies.delete(complete.messageId);
    resolve(await decode(complete.payload));
  }

  private async reconnectOnce(): Promise<void> {
    if (this.reconnecting || !this.device) return;
    this.reconnecting = true;
    try {
      await this.connect();
    } finally {
      this.reconnecting = false;
    }
  }
}
