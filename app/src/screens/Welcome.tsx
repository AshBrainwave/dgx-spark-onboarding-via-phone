export function Welcome({ onScan }: { onScan: () => void }) {
  return <section><h1>Set up your DGX Spark</h1><p>Scan the chassis QR code to begin.</p><button onClick={onScan}>Scan the QR code</button></section>;
}
