export const BLE_PAYLOAD_SIZE = 16;
export const BLE_HEADER_SIZE = 7;
const LAST_FRAGMENT = 1;

export function fragment(payload: Uint8Array, messageId: number): Uint8Array[] {
  const chunks = Math.max(1, Math.ceil(payload.length / BLE_PAYLOAD_SIZE));
  return Array.from({ length: chunks }, (_, sequence) => {
    const body = payload.slice(sequence * BLE_PAYLOAD_SIZE, (sequence + 1) * BLE_PAYLOAD_SIZE);
    const frame = new Uint8Array(BLE_HEADER_SIZE + body.length);
    const view = new DataView(frame.buffer);
    view.setUint8(0, 1); view.setUint8(1, sequence === chunks - 1 ? LAST_FRAGMENT : 0);
    view.setUint16(2, messageId, true); view.setUint16(4, sequence, true); view.setUint8(6, 0);
    frame.set(body, BLE_HEADER_SIZE); return frame;
  });
}

type Pending = { started: number; parts: Map<number, Uint8Array>; last?: number };
export class Reassembler {
  private pending = new Map<number, Pending>();
  constructor(private readonly timeoutMs = 10_000, private readonly clock = () => Date.now()) {}
  add(frame: Uint8Array): { messageId: number; payload: Uint8Array } | undefined {
    if (frame.length < BLE_HEADER_SIZE) throw new Error("short frame");
    const view = new DataView(frame.buffer, frame.byteOffset, frame.byteLength);
    if (view.getUint8(0) !== 1) throw new Error("unsupported frame version");
    const now = this.clock(); for (const [id, value] of this.pending) if (now - value.started >= this.timeoutMs) this.pending.delete(id);
    const messageId = view.getUint16(2, true); const sequence = view.getUint16(4, true);
    const value = this.pending.get(messageId) ?? { started: now, parts: new Map<number, Uint8Array>() };
    value.parts.set(sequence, frame.slice(BLE_HEADER_SIZE)); if (view.getUint8(1) & LAST_FRAGMENT) value.last = sequence; this.pending.set(messageId, value);
    if (value.last === undefined || Array.from({ length: value.last + 1 }, (_, index) => !value.parts.has(index)).some(Boolean)) return undefined;
    this.pending.delete(messageId); const size = Array.from(value.parts.values()).reduce((total, part) => total + part.length, 0); const payload = new Uint8Array(size);
    let offset = 0; for (let index = 0; index <= value.last; index += 1) { const part = value.parts.get(index)!; payload.set(part, offset); offset += part.length; }
    return { messageId, payload };
  }
}
