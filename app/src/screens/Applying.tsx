export const phases = ["associating", "authenticating", "dhcp", "verifying_internet", "online"];
export function Applying({ phase, elapsed }: { phase: string; elapsed: number }) { return <section><h2>Applying Wi-Fi settings</h2><p>{elapsed}s elapsed</p><ol>{phases.map(item => <li className={item === phase ? "active" : ""} key={item}>{item}</li>)}</ol><p className="muted">{phase}</p></section>; }
