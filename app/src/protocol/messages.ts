import { z } from "zod";

export const RequestEnvelope = z.object({
  v: z.literal(1),
  id: z.string().min(1),
  op: z.string().min(1),
  sid: z.string().nullable(),
  body: z.record(z.string(), z.unknown()),
});

export const ResponseEnvelope = z.object({
  v: z.literal(1),
  id: z.string().min(1),
  ok: z.boolean(),
});

export const Network = z.object({ ssid: z.string(), rssi: z.number(), bars: z.number(), security: z.string(), band: z.string(), unsupported: z.boolean().optional(), reason: z.string().optional() });
export type Network = z.infer<typeof Network>;
