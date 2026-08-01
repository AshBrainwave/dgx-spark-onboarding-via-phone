export function JoinAp({ ssid = "DGX-Spark-0001", password = "SparkSim2345", onJoined }: { ssid?: string; password?: string; onJoined: () => void }) {
  const uri = `WIFI:T:WPA;S:${ssid};P:${password};;`;
  return <section><h2>Join your Spark's Wi-Fi</h2><p>Open Wi-Fi settings, join this temporary network, then come back here.</p><a className="button" href={uri}>Join {ssid}</a><p className="credential">{ssid}<br />{password}</p><button onClick={onJoined}>I’m connected</button></section>;
}
