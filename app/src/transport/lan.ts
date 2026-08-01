import { HttpTransport } from "./http";

/** Discover the Spark after a non-concurrent AP-to-STA handoff.
 *
 * Bonjour is the fast path. Android Chrome's .local support is inconsistent, so
 * a bounded private-LAN sweep follows. Browsers cannot reveal the gateway subnet,
 * hence the three usual consumer-router ranges; manual IP is always available.
 */
export async function findSpark(mdnsName: string): Promise<HttpTransport | null> {
  const hosts = [mdnsName, ...candidateHosts()];
  const attempts = await Promise.all(hosts.map(async host => {
    const transport = new HttpTransport(`http://${host}:8080`);
    try {
      const probe = new AbortController();
      const timer = window.setTimeout(() => probe.abort(), 900);
      const response = await fetch(`http://${host}:8080/api/v1`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ v: 1, id: "handoff-probe", op: "device.info", sid: null, body: {} }),
        signal: probe.signal,
      });
      window.clearTimeout(timer);
      return response.ok ? transport : null;
    } catch {
      return null;
    }
  }));
  return attempts.find(Boolean) ?? null;
}

export function transportForManualIp(ip: string): HttpTransport {
  return new HttpTransport(`http://${ip.trim()}:8080`);
}

function candidateHosts(): string[] {
  const ranges = ["192.168.0", "192.168.1", "10.0.0"];
  return ranges.flatMap(range => Array.from({ length: 253 }, (_, index) => `${range}.${index + 2}`));
}
