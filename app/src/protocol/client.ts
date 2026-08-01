import type { Transport } from "../transport/types";
let count = 0;
export class Client { sid: string | null = null; constructor(private transport: Transport) {} async call(op: string, body: Record<string, unknown> = {}) { const result = await this.transport.request({ v: 1, id: `sim-${++count}`, op, sid: this.sid, body }); if (!result.ok) throw result.err; return result.body ?? {}; } async open() { const body = await this.call("session.open", { client_pubkey: "sim", nonce: "sim" }); this.sid = String(body.sid); } }
