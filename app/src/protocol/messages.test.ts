import fixtures from "../../../protocol/messages.json";
import { describe, expect, it } from "vitest";
import { RequestEnvelope, ResponseEnvelope } from "./messages";

describe("shared protocol fixtures", () => {
  it("validates every request and supplied response", () => {
    for (const fixture of fixtures) {
      expect(RequestEnvelope.parse(fixture.request)).toEqual(fixture.request);
      if ("response" in fixture) {
        expect(ResponseEnvelope.parse(fixture.response).ok).toBe(true);
      }
    }
  });
});
