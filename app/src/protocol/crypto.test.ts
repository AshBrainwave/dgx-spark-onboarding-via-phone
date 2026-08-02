import vectors from "../../../protocol/crypto-vectors.json";
import { describe, expect, it, vi } from "vitest";
import { createKeyPair, deriveSessionKey, encryptPsk, importPrivateKey } from "./crypto";

describe("shared crypto vectors", () => {
  it("matches the Python-produced AES-GCM ciphertext", async () => {
    for (const vector of vectors) {
      const privateKey = await importPrivateKey(vector.client_private_pkcs8);
      const key = await deriveSessionKey(privateKey, vector.device_public, vector.client_nonce, vector.device_nonce);
      await expect(encryptPsk(key, vector.counter, vector.ssid, vector.psk)).resolves.toBe(vector.ciphertext);
    }
  });

  it("generates X25519 keys without secure-context SubtleCrypto", async () => {
    const getRandomValues = globalThis.crypto.getRandomValues.bind(globalThis.crypto);
    vi.stubGlobal("crypto", { getRandomValues });
    try {
      const pair = await createKeyPair();
      expect(pair.privateKey).toHaveLength(32);
      expect(pair.publicKey).toHaveLength(32);
    } finally {
      vi.unstubAllGlobals();
    }
  });
});
