export function JoinAp({ ssid, password, onJoined }: { ssid?: string; password?: string; onJoined: () => void }) {
  const uri = ssid && password ? `WIFI:T:WPA;S:${ssid};P:${password};;` : null;
  return <section><h2>Join your Spark's Wi-Fi</h2><p>Open Wi-Fi settings, join the temporary network from the Spark's QR code, then come back here.</p>{uri && <><a className="button" href={uri}>Join {ssid}</a><p className="credential">{ssid}<br />{password}</p></>}<button onClick={onJoined}>I’m connected</button></section>;
}
