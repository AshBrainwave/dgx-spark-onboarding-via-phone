import { describe, expect, it } from "vitest";
import { fragment, Reassembler } from "./framing";
describe("BLE framing", () => {
  it("reassembles 16-byte frames in any order", () => { const input = new TextEncoder().encode("a payload longer than sixteen bytes"); const receiver = new Reassembler(); let result; for (const frame of fragment(input, 42).reverse()) result ??= receiver.add(frame); expect(new TextDecoder().decode(result?.payload)).toBe("a payload longer than sixteen bytes"); });
  it("drops incomplete messages after ten seconds", () => { let now = 0; const receiver = new Reassembler(10_000, () => now); receiver.add(fragment(new Uint8Array(32), 1)[0]); now = 10_000; expect(receiver.add(fragment(new Uint8Array([1]), 2)[0])).toBeDefined(); });
});
