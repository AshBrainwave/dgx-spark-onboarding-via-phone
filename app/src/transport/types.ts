export interface Transport { request(message: RequestMessage): Promise<ResponseMessage>; }
export type RequestMessage = { v: 1; id: string; op: string; sid: string | null; body: Record<string, unknown> };
export type ResponseMessage = { v: 1; id: string; ok: boolean; body?: Record<string, unknown>; err?: { code: string; msg: string } };
