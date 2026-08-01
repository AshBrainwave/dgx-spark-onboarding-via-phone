import { fragment, Reassembler } from "../protocol/framing";
import type { RequestMessage, ResponseMessage, Transport } from "./types";
/** Radio-free transport that exercises the exact BLE framing implementation. */
export class LoopbackTransport implements Transport {
  private nextId = 0;
  constructor(private readonly handler: (message: RequestMessage) => Promise<ResponseMessage>) {}
  async request(message: RequestMessage): Promise<ResponseMessage> { const receiver = new Reassembler(); let complete: Uint8Array | undefined; for (const frame of fragment(new TextEncoder().encode(JSON.stringify(message)), ++this.nextId)) complete = receiver.add(frame)?.payload ?? complete; if (!complete) throw new Error("BLE framing did not complete"); return this.handler(JSON.parse(new TextDecoder().decode(complete)) as RequestMessage); }
}
