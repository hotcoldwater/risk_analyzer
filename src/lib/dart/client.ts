import { AppError, requireValue } from "../utils/errors";
import type { DartStatusResponse } from "../../types/dart";

const DART_API_BASE_URL = "https://opendart.fss.or.kr/api";
const DART_ERROR_URL_FRAGMENT = "/error1.html";

function createDartCredentialError() {
  return new AppError(
    "DART API 인증키가 올바르지 않거나 DART 응답이 비정상입니다.",
    "DART_INVALID_CREDENTIAL_OR_RESPONSE",
    400
  );
}

export async function dartFetch<T extends DartStatusResponse>(
  endpoint: string,
  params: Record<string, string>,
  apiKey: string | undefined
): Promise<T> {
  const verifiedApiKey = requireValue(
    apiKey,
    "DART API 인증키가 설정되지 않았습니다.",
    "MISSING_DART_API_KEY"
  );
  const url = new URL(`${DART_API_BASE_URL}/${endpoint}`);

  url.searchParams.set("crtfc_key", verifiedApiKey);

  for (const [key, value] of Object.entries(params)) {
    url.searchParams.set(key, value);
  }

  let response: Response;

  try {
    response = await fetch(url.toString(), {
      method: "GET",
      headers: {
        Accept: "application/json"
      },
      cache: "no-store"
    });
  } catch (error) {
    if (
      error instanceof Error &&
      /redirect/i.test(error.message)
    ) {
      throw createDartCredentialError();
    }

    throw error;
  }

  if (response.url.includes(DART_ERROR_URL_FRAGMENT)) {
    throw createDartCredentialError();
  }

  if (!response.ok) {
    throw new AppError("DART API 요청 중 오류가 발생했습니다.", "DART_HTTP_ERROR", response.status);
  }

  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    throw createDartCredentialError();
  }

  const data = (await response.json()) as T;

  if (data.status !== "000") {
    throw new AppError(
      data.message || "DART API 요청 중 오류가 발생했습니다.",
      "DART_API_ERROR",
      400
    );
  }

  return data;
}
