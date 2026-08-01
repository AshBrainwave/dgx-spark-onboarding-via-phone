import { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { Client, ProtocolError } from "./protocol/client";
import type { Network } from "./protocol/messages";
import { HttpTransport } from "./transport/http";
import { BleTransport, shouldUseBle } from "./transport/ble";
import { Applying } from "./screens/Applying";
import { ChooseNetwork } from "./screens/ChooseNetwork";
import { Connecting } from "./screens/Connecting";
import { ErrorScreen, errorCopy, type ErrorCode } from "./screens/errors";
import { JoinAp } from "./screens/JoinAp";
import { Password } from "./screens/Password";
import { QrScanner } from "./screens/QrScanner";
import { Reconnect } from "./screens/Reconnect";
import { Success } from "./screens/Success";
import { Welcome } from "./screens/Welcome";
import "./style.css";

const client = new Client(new HttpTransport());
const bleTransport = new BleTransport();
type Screen = "welcome" | "qr" | "join" | "connecting" | "networks" | "password" | "applying" | "reconnect" | "success" | "error";
const knownError = (value: string): ErrorCode => value in errorCopy ? value as ErrorCode : "PORTAL_UNREACHABLE";

function App() {
  const params = new URLSearchParams(location.search);
  const devScreen = params.get("screen") as Screen | null;
  const devError = params.get("error");
  const [screen, setScreen] = useState<Screen>(devScreen ?? "welcome");
  const [networks, setNetworks] = useState<Network[]>([]);
  const [selected, setSelected] = useState<Network | null>(null);
  const [scannedAt, setScannedAt] = useState("");
  const [phase, setPhase] = useState("idle");
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<ErrorCode>(knownError(devError ?? "PORTAL_UNREACHABLE"));
  const [ip, setIp] = useState("");
  const [connectingTransport, setConnectingTransport] = useState<"BLE" | "portal">("portal");
  const concurrent = params.get("concurrent") !== "0";
  const selectedSsid = selected?.ssid ?? "Hidden network";
  const fail = (reason: unknown) => { setError(knownError(reason instanceof ProtocolError ? reason.code : "PORTAL_UNREACHABLE")); setScreen("error"); };
  const onQrParsed = () => {
    const ios = /iPad|iPhone|iPod/.test(navigator.userAgent);
    if (!ios && shouldUseBle()) {
      setConnectingTransport("BLE");
      setScreen("connecting");
    }
    else setScreen("join");
  };
  async function openAndScan(useBle = false) {
    setScreen("connecting");
    try {
      if (useBle) {
        // Called from Connecting's button handler; requestDevice requires this gesture.
        await bleTransport.chooseDevice();
        client.setTransport(bleTransport);
      } else {
        client.setTransport(new HttpTransport());
      }
      const info = await client.call("device.info");
      const qrPubkey = params.get("pubkey") ?? String(info.pubkey);
      await client.open(qrPubkey);
      await refresh();
    } catch (reason) {
      fail(reason);
    }
  }
  async function refresh() {
    try {
      const result = await client.call("wifi.scan", { force: true });
      setNetworks(result.networks as Network[]);
      setScannedAt(String(result.scanned_at));
      setScreen("networks");
    } catch (reason) {
      fail(reason);
    }
  }
  async function connect(password: string) {
    try {
      await client.connectWifi(selectedSsid, selected?.security ?? "wpa2-psk", password, !selected);
      setElapsed(0);
      setScreen("applying");
    } catch (reason) {
      fail(reason);
    }
  }
  useEffect(() => { if (screen !== "applying") return; const started = Date.now(); const timer = setInterval(async () => { setElapsed(Math.floor((Date.now() - started) / 1000)); try { const status = await client.call("wifi.status"); setPhase(String(status.phase)); if (status.phase === "online") { setIp(String(status.ip)); setScreen(concurrent ? "success" : "reconnect"); } if (status.phase === "failed") fail(new ProtocolError(String(status.err), "Wi-Fi failed")); } catch (reason) { fail(reason); } }, 500); return () => clearInterval(timer); }, [screen, concurrent]);
  useEffect(() => { if (screen !== "reconnect") return; const timer = setTimeout(() => setScreen("success"), 5000); return () => clearTimeout(timer); }, [screen]);
  const route = devScreen ?? screen;
  const demoNetworks: Network[] = [{ ssid: "Home Wi-Fi", rssi: -40, bars: 4, security: "wpa2-psk", band: "2.4ghz" }];
  const content = useMemo(() => {
    switch (route) {
      case "welcome": return <Welcome onScan={() => setScreen("qr")} />;
      case "qr": return <QrScanner onParsed={onQrParsed} />;
      case "join": return <JoinAp onJoined={() => openAndScan(false)} />;
      case "connecting": return <Connecting transport={connectingTransport} onContinue={() => openAndScan(connectingTransport === "BLE")} />;
      case "networks": return <ChooseNetwork networks={networks.length ? networks : demoNetworks} scannedAt={scannedAt} onChoose={n => { setSelected(n); setScreen("password"); }} onRefresh={refresh} onOther={() => { setSelected(null); setScreen("password"); }} />;
      case "password": return <Password ssid={selectedSsid} onSubmit={connect} />;
      case "applying": return <Applying phase={phase} elapsed={elapsed} />;
      case "reconnect": return <Reconnect ssid={selectedSsid} seconds={20} />;
      case "success": return <Success ip={ip || "192.168.1.44"} hostname="dgx-spark-sim" onName={async name => { try { await client.call("device.rename", { name }); } catch { /* Naming is optional after success. */ } }} />;
      case "error": return <ErrorScreen code={error} ssid={selected?.ssid} onBack={() => {
        const target = errorCopy[error].target;
        if (target === "password") setScreen("password");
        else if (target === "join") setScreen("join");
        else if (target === "abort") setScreen("welcome");
        else if (target === "manual") setScreen("join");
        else if (target === "retry" && error === "WIFI_NO_INTERNET") setScreen("success");
        else if (target === "retry") openAndScan();
        else refresh();
      }} />;
    }
  }, [route, networks, scannedAt, phase, elapsed, error, ip, selected]);
  return <main>
    {content}
    <p className="dev-links">
      Review routes: {(["welcome", "qr", "join", "connecting", "networks", "password", "applying", "reconnect", "success", "error"] as Screen[]).map(name => <a key={name} href={`?screen=${name}`}>{name}</a>)}
    </p>
  </main>;
}
createRoot(document.getElementById("root")!).render(<App />);
