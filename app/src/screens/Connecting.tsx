export function Connecting({ transport }: { transport: "BLE" | "portal" }) {
  return <section><h2>Connecting to Spark</h2><ol><li>Checking the QR device key</li><li>{transport === "BLE" ? "Opening Bluetooth secure channel" : "Opening secure portal channel"}</li><li>Loading available Wi-Fi networks</li></ol></section>;
}
