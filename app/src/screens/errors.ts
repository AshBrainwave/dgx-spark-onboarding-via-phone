export const errorCopy: Record<string, { title: string; detail: string; action: string }> = {
  WIFI_AUTH_FAILED: { title: "That password didn't work", detail: "Check the password and try again.", action: "Back to password" },
  WIFI_SSID_NOT_FOUND: { title: "Couldn't find that network", detail: "It may be out of range or unavailable.", action: "Rescan networks" },
  WIFI_WEAK_SIGNAL: { title: "Signal is too weak", detail: "Move the Spark closer to your router, then retry.", action: "Choose network" },
  WIFI_DHCP_FAILED: { title: "Couldn't get an address", detail: "The Spark joined the network but did not receive an IP address.", action: "Try again" },
  WIFI_CAPTIVE_PORTAL: { title: "This network needs a sign-in", detail: "Spark cannot complete browser captive-portal sign-in.", action: "Choose another network" },
  WIFI_NO_INTERNET: { title: "No internet connection", detail: "The Spark is on your LAN but cannot reach the internet.", action: "Continue on LAN" },
  SESSION_BUSY: { title: "Spark is being set up", detail: "Another phone currently owns this setup session.", action: "Try again" },
  PORTAL_UNREACHABLE: { title: "You're not connected to Spark", detail: "Join the DGX Spark access point and return here.", action: "Show join instructions" },
};
