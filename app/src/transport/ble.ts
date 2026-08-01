import type { Transport } from "./types";
export class BleTransport implements Transport { async request(): Promise<never> { throw new Error("BLE is scheduled for v0.3-ble"); } }
