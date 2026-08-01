export type Phase =
  | "idle"
  | "scan_qr"
  | "qr_parsed"
  | "ble_request_device"
  | "ble_connecting"
  | "show_join_ap"
  | "portal_loaded"
  | "secure_channel"
  | "wifi_list"
  | "creds_entry"
  | "applying"
  | "reconnect"
  | "verifying_from_lan"
  | "claimed"
  | "success"
  | "failure";

export type Event =
  | "SCAN_QR" | "QR_PARSED" | "REQUEST_BLE" | "BLE_CONNECTED" | "SHOW_AP"
  | "PORTAL_LOADED" | "SECURE" | "NETWORK_SELECTED" | "APPLY" | "HANDOFF"
  | "LAN_VERIFIED" | "CLAIMED" | "COMPLETE" | "FAIL" | "BACK_LIST" | "BACK_CREDS";

export interface State { phase: Phase; error?: string }
export interface Platform { ios: boolean; bleAvailable: boolean }

const transitions: Partial<Record<Phase, Partial<Record<Event, Phase>>>> = {
  idle: { SCAN_QR: "scan_qr" },
  scan_qr: { QR_PARSED: "qr_parsed" },
  qr_parsed: { REQUEST_BLE: "ble_request_device", SHOW_AP: "show_join_ap" },
  ble_request_device: { BLE_CONNECTED: "ble_connecting", FAIL: "failure" },
  ble_connecting: { SECURE: "secure_channel", FAIL: "failure" },
  show_join_ap: { PORTAL_LOADED: "portal_loaded" },
  portal_loaded: { SECURE: "secure_channel", FAIL: "failure" },
  secure_channel: { NETWORK_SELECTED: "wifi_list", FAIL: "failure" },
  wifi_list: { NETWORK_SELECTED: "creds_entry", FAIL: "failure" },
  creds_entry: { APPLY: "applying", BACK_LIST: "wifi_list", FAIL: "failure" },
  applying: { HANDOFF: "reconnect", CLAIMED: "claimed", FAIL: "failure" },
  reconnect: { LAN_VERIFIED: "verifying_from_lan", FAIL: "failure" },
  verifying_from_lan: { CLAIMED: "claimed", FAIL: "failure" },
  claimed: { COMPLETE: "success" },
  failure: { BACK_LIST: "wifi_list", BACK_CREDS: "creds_entry" },
};

export function chooseTransport(platform: Platform): Event {
  return !platform.ios && platform.bleAvailable ? "REQUEST_BLE" : "SHOW_AP";
}

export function transition(state: State, event: Event, error?: string): State {
  const next = transitions[state.phase]?.[event];
  if (!next) throw new Error(`Invalid transition: ${state.phase} -> ${event}`);
  return next === "failure" ? { phase: next, error } : { phase: next };
}
