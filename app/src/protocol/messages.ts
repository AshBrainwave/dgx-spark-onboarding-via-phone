import { z } from "zod";
export const Network = z.object({ ssid: z.string(), rssi: z.number(), bars: z.number(), security: z.string(), band: z.string(), unsupported: z.boolean().optional(), reason: z.string().optional() });
export type Network = z.infer<typeof Network>;
