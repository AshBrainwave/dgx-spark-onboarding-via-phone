import type { ReactNode } from "react";

export type ErrorCode =
  | "WIFI_AUTH_FAILED" | "WIFI_SSID_NOT_FOUND" | "WIFI_WEAK_SIGNAL" | "WIFI_DHCP_FAILED"
  | "WIFI_NO_INTERNET" | "WIFI_CAPTIVE_PORTAL" | "WIFI_ENTERPRISE_UNSUPPORTED" | "WIFI_BAND_MISMATCH"
  | "SESSION_BUSY" | "SESSION_EXPIRED" | "PUBKEY_MISMATCH" | "BLE_DISCONNECTED"
  | "PORTAL_UNREACHABLE" | "DEVICE_LOST_AFTER_HANDOFF";

export interface ErrorDetails { title: string; detail: (ssid?: string) => string; action: string; target: "list" | "password" | "join" | "retry" | "manual" | "abort" }
export const errorCopy: Record<ErrorCode, ErrorDetails> = {
  WIFI_AUTH_FAILED: { title: "That password didn't work", detail: s => `That password didn't work for ${s ?? "this network"}.`, action: "Back to password", target: "password" },
  WIFI_SSID_NOT_FOUND: { title: "Couldn't find that network", detail: () => "The network is gone or out of range. We will scan again.", action: "Rescan networks", target: "list" },
  WIFI_WEAK_SIGNAL: { title: "Signal is too weak", detail: () => "Move the Spark closer to your router, then try again.", action: "Choose another network", target: "list" },
  WIFI_DHCP_FAILED: { title: "Couldn't get an address", detail: () => "The Spark joined Wi-Fi but did not receive an address. Try again or reboot the router.", action: "Try again", target: "password" },
  WIFI_NO_INTERNET: { title: "No internet connection", detail: () => "The Spark is on your LAN but cannot reach the internet. LAN-only setup is okay.", action: "Continue on LAN", target: "retry" },
  WIFI_CAPTIVE_PORTAL: { title: "This network needs a sign-in", detail: () => "Choose another network: the Spark cannot complete a browser sign-in.", action: "Choose another network", target: "list" },
  WIFI_ENTERPRISE_UNSUPPORTED: { title: "Enterprise Wi-Fi isn't supported yet", detail: () => "802.1X networks need Ethernet for this PoC.", action: "Choose another network", target: "list" },
  WIFI_BAND_MISMATCH: { title: "This network uses an unsupported band", detail: () => "Choose its 2.4 GHz twin if your router shows one.", action: "Choose another network", target: "list" },
  SESSION_BUSY: { title: "Spark is being set up", detail: () => "Another phone is claiming it. Wait up to 90 seconds, then retry.", action: "Try again", target: "retry" },
  SESSION_EXPIRED: { title: "Setup window closed", detail: () => "Press the Spark reset button to reopen the 15-minute setup window.", action: "Show join instructions", target: "join" },
  PUBKEY_MISMATCH: { title: "This isn't the Spark you scanned", detail: () => "The QR key does not match the device key. Do not continue.", action: "Start over", target: "abort" },
  BLE_DISCONNECTED: { title: "Bluetooth disconnected", detail: () => "We retried once. Move closer to the Spark and try again.", action: "Try again", target: "retry" },
  PORTAL_UNREACHABLE: { title: "You're not connected to Spark", detail: () => "Join the DGX Spark access point, then return here.", action: "Show join instructions", target: "join" },
  DEVICE_LOST_AFTER_HANDOFF: { title: "Couldn't find Spark after Wi-Fi changed", detail: () => "Try its manual IP address, or reconnect to the Spark access point.", action: "Enter IP address", target: "manual" },
};

export function ErrorScreen({ code, ssid, onBack }: { code: ErrorCode; ssid?: string; onBack: () => void }): ReactNode {
  const copy = errorCopy[code];
  return <section><h2>{copy.title}</h2><p>{copy.detail(ssid)}</p><button onClick={onBack}>{copy.action}</button></section>;
}
