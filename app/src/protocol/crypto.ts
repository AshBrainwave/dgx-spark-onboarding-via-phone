import { gcm } from "@noble/ciphers/aes.js";
import { x25519 } from "@noble/curves/ed25519.js";
import { hkdf } from "@noble/hashes/hkdf.js";
import { sha256 } from "@noble/hashes/sha2.js";

export const protocolInfo = "dgx-spark-prov-v1";
const encoder = new TextEncoder();
const x25519Pkcs8Prefix = Uint8Array.from([
  0x30, 0x2e, 0x02, 0x01, 0x00, 0x30, 0x05, 0x06,
  0x03, 0x2b, 0x65, 0x6e, 0x04, 0x22, 0x04, 0x20,
]);

export const b64url = (value: Uint8Array) => btoa(String.fromCharCode(...value)).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", "");
export const unb64url = (value: string) => Uint8Array.from(atob(value.replaceAll("-", "+").replaceAll("_", "/") + "=".repeat((4 - value.length % 4) % 4)), char => char.charCodeAt(0));

export async function createKeyPair() {
  const pair = x25519.keygen();
  return { privateKey: pair.secretKey, publicKey: pair.publicKey };
}

export async function importPrivateKey(encoded: string) {
  const pkcs8 = unb64url(encoded);
  const prefixMatches = x25519Pkcs8Prefix.every((byte, index) => pkcs8[index] === byte);
  if (pkcs8.length !== x25519Pkcs8Prefix.length + 32 || !prefixMatches) {
    throw new Error("Invalid X25519 PKCS8 private key");
  }
  return pkcs8.slice(x25519Pkcs8Prefix.length);
}

export async function exportPublicKey(key: Uint8Array) {
  return b64url(key);
}

export async function deriveSessionKey(privateKey: Uint8Array, peer: string, clientNonce: string, deviceNonce: string) {
  const sharedSecret = x25519.getSharedSecret(privateKey, unb64url(peer));
  const salt = new Uint8Array([...unb64url(clientNonce), ...unb64url(deviceNonce)]);
  return hkdf(sha256, sharedSecret, salt, encoder.encode(protocolInfo), 32);
}

export async function encryptPsk(key: Uint8Array, counter: number, ssid: string, psk: string) {
  const nonce = new Uint8Array(12);
  new DataView(nonce.buffer).setUint32(8, counter);
  const encrypted = gcm(key, nonce, encoder.encode(ssid)).encrypt(encoder.encode(psk));
  return b64url(new Uint8Array([...nonce, ...encrypted]));
}
