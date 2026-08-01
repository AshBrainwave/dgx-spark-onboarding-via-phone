export const protocolInfo = "dgx-spark-prov-v1";
const encoder = new TextEncoder();
const b64url = (value: Uint8Array) => btoa(String.fromCharCode(...value)).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", "");
const unb64url = (value: string) => Uint8Array.from(atob(value.replaceAll("-", "+").replaceAll("_", "/") + "=".repeat((4 - value.length % 4) % 4)), char => char.charCodeAt(0));

export async function createKeyPair() { return crypto.subtle.generateKey({ name: "X25519" }, true, ["deriveBits"]) as Promise<CryptoKeyPair>; }
export async function exportPublicKey(key: CryptoKey) { return b64url(new Uint8Array(await crypto.subtle.exportKey("raw", key))); }
export async function deriveSessionKey(privateKey: CryptoKey, peer: string, clientNonce: string, deviceNonce: string) {
  const publicKey = await crypto.subtle.importKey("raw", unb64url(peer), { name: "X25519" }, false, []);
  const bits = await crypto.subtle.deriveBits({ name: "X25519", public: publicKey }, privateKey, 256);
  const material = await crypto.subtle.importKey("raw", bits, "HKDF", false, ["deriveKey"]);
  return crypto.subtle.deriveKey({ name: "HKDF", hash: "SHA-256", salt: encoder.encode(clientNonce + deviceNonce), info: encoder.encode(protocolInfo) }, material, { name: "AES-GCM", length: 256 }, false, ["encrypt"]);
}
export async function encryptPsk(key: CryptoKey, counter: number, ssid: string, psk: string) {
  const nonce = new Uint8Array(12); new DataView(nonce.buffer).setUint32(8, counter);
  const encrypted = await crypto.subtle.encrypt({ name: "AES-GCM", iv: nonce, additionalData: encoder.encode(ssid) }, key, encoder.encode(psk));
  return b64url(new Uint8Array([...nonce, ...new Uint8Array(encrypted)]));
}
