import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { JoinAp } from "./JoinAp";
import { errorCopy } from "./errors";

describe("production recovery UI", () => {
  it("never invents simulator Wi-Fi credentials", () => {
    const html = renderToStaticMarkup(<JoinAp onJoined={() => undefined} />);

    expect(html).toContain("Spark&#x27;s QR code");
    expect(html).not.toContain("DGX-Spark-0001");
    expect(html).not.toContain("SparkSim2345");
    expect(html).not.toContain("WIFI:");
  });

  it("retries an expired session only after reset", () => {
    expect(errorCopy.SESSION_EXPIRED.action).toBe("Try again after reset");
    expect(errorCopy.SESSION_EXPIRED.target).toBe("retry");
  });
});
