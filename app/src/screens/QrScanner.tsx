import { useEffect, useRef, useState } from "react";
import { BrowserQRCodeReader } from "@zxing/browser";

export function QrScanner({ onParsed }: { onParsed: (value: string) => void }) {
  const video = useRef<HTMLVideoElement>(null); const [manual, setManual] = useState("");
  useEffect(() => { let cancelled = false; let stream: MediaStream | undefined; let stopFallback: (() => void) | undefined;
    async function scan() { try { stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } }); if (video.current) video.current.srcObject = stream;
      if (!("BarcodeDetector" in window)) { const reader = new BrowserQRCodeReader(); const controls = await reader.decodeFromVideoDevice(undefined, video.current!, result => { if (result && !cancelled) onParsed(result.getText()); }); stopFallback = () => controls.stop(); return; }
      const detector = new (window as typeof window & { BarcodeDetector: new (o: { formats: string[] }) => { detect(v: HTMLVideoElement): Promise<{ rawValue: string }[]> } }).BarcodeDetector({ formats: ["qr_code"] });
      const tick = async () => { if (cancelled || !video.current) return; const found = await detector.detect(video.current); if (found[0]) onParsed(found[0].rawValue); else requestAnimationFrame(tick); }; tick();
    } catch { /* Manual entry remains available. */ } }
    scan(); return () => { cancelled = true; stopFallback?.(); stream?.getTracks().forEach(track => track.stop()); };
  }, [onParsed]);
  return <section><h2>Scan the QR code</h2><video ref={video} autoPlay muted playsInline /><p className="muted">Uses BarcodeDetector where available and @zxing/browser on older browsers.</p><label>Pairing code<input maxLength={8} value={manual} onChange={e => setManual(e.target.value.toUpperCase())} placeholder="8-character code" /></label><button disabled={manual.length !== 8} onClick={() => onParsed(manual)}>Continue</button><button className="secondary" onClick={() => onParsed("SIMULATED")}>Use simulator QR</button></section>;
}
