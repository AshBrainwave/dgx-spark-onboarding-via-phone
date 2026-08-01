import { expect, it } from "vitest";
import { LoopbackTransport } from "./loopback";
it("pipes a request through fragmented loopback frames", async () => { const transport = new LoopbackTransport(async message => ({ v: 1, id: message.id, ok: true, body: { echoed: message.op } })); await expect(transport.request({ v: 1, id: "large-request", op: "wifi.scan", sid: null, body: { padding: "x".repeat(80) } })).resolves.toMatchObject({ body: { echoed: "wifi.scan" } }); });
