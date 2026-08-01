import vectors from "../../../protocol/crypto-vectors.json";
import { describe, expect, it } from "vitest";
import { deriveSessionKey, encryptPsk, importPrivateKey } from "./crypto";

describe("shared crypto vectors", () => {
  it("matches the Python-produced AES-GCM ciphertext", async () => {
    for (const vector of vectors) {
      const privateKey = await importPrivateKey(vector.client_private_pkcs8);
      const key = await deriveSessionKey(privateKey, vector.device_public, vector.client_nonce, vector.device_nonce);
      await expect(encryptPsk(key, vector.counter, vector.ssid, vector.psk)).resolves.toBe(vector.ciphertext);
    }
  });
});
