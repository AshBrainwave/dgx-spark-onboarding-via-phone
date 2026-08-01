import { describe, expect, it } from "vitest";
import { chooseTransport, transition, type State } from "./machine";

describe("onboarding machine", () => {
  it("takes Android BLE through a secure channel", () => {
    let state: State = { phase: "idle" };
    for (const event of ["SCAN_QR", "QR_PARSED", chooseTransport({ ios: false, bleAvailable: true }), "BLE_CONNECTED", "SECURE"] as const) state = transition(state, event);
    expect(state.phase).toBe("secure_channel");
  });
  it("takes iOS through the AP portal", () => {
    let state: State = { phase: "qr_parsed" };
    state = transition(state, chooseTransport({ ios: true, bleAvailable: true }));
    state = transition(state, "PORTAL_LOADED");
    expect(state.phase).toBe("portal_loaded");
  });
  it("never permits an error to return to QR scanning", () => {
    let state = transition({ phase: "creds_entry" }, "FAIL", "WIFI_AUTH_FAILED");
    state = transition(state, "BACK_CREDS");
    expect(state.phase).toBe("creds_entry");
    expect(() => transition({ phase: "failure" }, "SCAN_QR")).toThrow();
  });
});
