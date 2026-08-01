import { useState } from "react";

export function Reconnect({
  ssid,
  seconds,
  onManualIp,
}: {
  ssid: string;
  seconds: number;
  onManualIp: (ip: string) => void;
}) {
  const [ip, setIp] = useState("");
  return <section>
    <h2>Reconnect to {ssid}</h2>
    <p>The Spark needs to leave its setup Wi-Fi. Join your home network now; we’ll look for it for {seconds} seconds.</p>
    <p className="countdown">{seconds}</p>
    <label>
      Can’t find it? Enter the Spark’s LAN IP
      <input inputMode="decimal" placeholder="192.168.1.44" value={ip} onChange={event => setIp(event.target.value)} />
    </label>
    <button disabled={!ip.trim()} onClick={() => onManualIp(ip)}>Try this IP</button>
  </section>;
}
