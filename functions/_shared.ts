import { AppError, toKoreanErrorMessage } from "../src/lib/utils/errors";

export type PagesEnv = {
  DART_API_KEY?: string;
};

export type PagesContext<Env = PagesEnv> = {
  request: Request;
  env: Env;
  params: Record<string, string | string[]>;
  waitUntil: (promise: Promise<unknown>) => void;
  next: () => Promise<Response>;
  data: unknown;
};

export function json(data: unknown, init?: ResponseInit) {
  return new Response(JSON.stringify(data), {
    ...init,
    headers: {
      "content-type": "application/json; charset=utf-8",
      ...(init?.headers ?? {})
    }
  });
}

export function ok(data: unknown, init?: ResponseInit) {
  return json({ success: true, data }, init);
}

export function fail(error: unknown, fallbackStatus = 400) {
  const status = error instanceof AppError ? error.status : fallbackStatus;
  return json(
    {
      success: false,
      error: toKoreanErrorMessage(error)
    },
    { status }
  );
}
