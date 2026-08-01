import { useState } from "react";
export function Password({ ssid, onSubmit }: { ssid: string; onSubmit: (password: string) => void }) {
  const [password, setPassword] = useState(""); const [visible, setVisible] = useState(false);
  return <section><h2>Password for {ssid}</h2><input aria-label="Wi-Fi password" autoComplete="current-password" autoCapitalize="none" autoCorrect="off" spellCheck={false} type={visible ? "text" : "password"} value={password} onChange={e => setPassword(e.target.value)} /><label><input type="checkbox" checked={visible} onChange={e => setVisible(e.target.checked)} /> Show password</label><p className={password.length > 0 && (password.length < 8 || password.length > 63) ? "warning" : "muted"}>{password.length}/63 characters — WPA2 PSK is 8–63 characters.</p><button disabled={password.length < 8 || password.length > 63} onClick={() => onSubmit(password)}>Send credentials</button></section>;
}
