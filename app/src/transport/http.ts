import type { RequestMessage, ResponseMessage, Transport } from "./types";
export class HttpTransport implements Transport {
  constructor(private readonly baseUrl = import.meta.env.VITE_AGENT_URL ?? (import.meta.env.MODE === "portal" ? "" : "http://127.0.0.1:8080")) {}

  async request(message: RequestMessage): Promise<ResponseMessage> {
    const response = await fetch(`${this.baseUrl}/api/v1`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(message) });
    return response.json() as Promise<ResponseMessage>;
  }
}
