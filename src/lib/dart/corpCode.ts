import { unzipSync, strFromU8 } from "fflate";
import { XMLParser } from "fast-xml-parser";
import { AppError, requireValue } from "../utils/errors";
import type { CorpSummary } from "../../types/dart";

type CorpCodeItem = {
  corp_code?: string;
  corp_name?: string;
  stock_code?: string;
  modify_date?: string;
};

let corpCache: CorpSummary[] | null = null;
const DART_ERROR_URL_FRAGMENT = "/error1.html";

function normalizeQuery(value: string) {
  return value.trim().toLowerCase().replace(/\s+/g, "");
}

async function loadCorpCodesWithKey(apiKey: string | undefined): Promise<CorpSummary[]> {
  if (corpCache) {
    return corpCache;
  }

  const verifiedApiKey = requireValue(
    apiKey,
    "DART API 인증키가 설정되지 않았습니다.",
    "MISSING_DART_API_KEY"
  );
  const url = new URL("https://opendart.fss.or.kr/api/corpCode.xml");
  url.searchParams.set("crtfc_key", verifiedApiKey);

  let response: Response;

  try {
    response = await fetch(url.toString(), {
      method: "GET"
    });
  } catch (error) {
    if (error instanceof Error && /redirect/i.test(error.message)) {
      throw new AppError(
        "DART API 인증키가 올바르지 않거나 기업코드 응답이 비정상입니다.",
        "DART_CORP_CODE_REDIRECT_ERROR",
        400
      );
    }

    throw error;
  }

  if (response.url.includes(DART_ERROR_URL_FRAGMENT)) {
    throw new AppError(
      "DART API 인증키가 올바르지 않거나 기업코드 응답이 비정상입니다.",
      "DART_CORP_CODE_ERROR_PAGE",
      400
    );
  }

  if (!response.ok) {
    throw new AppError("DART API 요청 중 오류가 발생했습니다.", "DART_CORP_CODE_HTTP_ERROR", 500);
  }

  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("text/html")) {
    throw new AppError(
      "DART API 인증키가 올바르지 않거나 기업코드 응답이 비정상입니다.",
      "DART_CORP_CODE_HTML_ERROR",
      400
    );
  }

  const buffer = new Uint8Array(await response.arrayBuffer());
  let unzipped: Record<string, Uint8Array>;

  try {
    unzipped = unzipSync(buffer);
  } catch {
    throw new AppError(
      "기업코드 ZIP 응답을 읽지 못했습니다. DART 응답을 다시 확인해 주세요.",
      "DART_CORP_CODE_UNZIP_ERROR",
      400
    );
  }

  const xmlEntry = Object.values(unzipped)[0];

  if (!xmlEntry) {
    throw new AppError("기업코드 데이터를 읽지 못했습니다.", "DART_CORP_CODE_PARSE_ERROR", 500);
  }

  const xml = strFromU8(xmlEntry);
  const parser = new XMLParser({
    ignoreAttributes: true,
    trimValues: true
  });
  const parsed = parser.parse(xml) as {
    result?: {
      list?: CorpCodeItem | CorpCodeItem[];
    };
  };

  const list = parsed.result?.list;
  const items = Array.isArray(list) ? list : list ? [list] : [];

  corpCache = items
    .map((item) => ({
      corpCode: item.corp_code ?? "",
      corpName: item.corp_name ?? "",
      stockCode: item.stock_code?.trim() || undefined,
      modifyDate: item.modify_date
    }))
    .filter((item) => item.corpCode && item.corpName);

  return corpCache;
}

export async function searchCorporationsByName(
  query: string,
  apiKey: string | undefined
): Promise<CorpSummary[]> {
  const normalizedQuery = normalizeQuery(query);

  if (!normalizedQuery) {
    return [];
  }

  const corpCodes = await loadCorpCodesWithKey(apiKey);
  return corpCodes
    .filter((corp) => normalizeQuery(corp.corpName).includes(normalizedQuery))
    .sort((a, b) => {
      const aExact = normalizeQuery(a.corpName) === normalizedQuery ? -1 : 0;
      const bExact = normalizeQuery(b.corpName) === normalizedQuery ? -1 : 0;
      if (aExact !== bExact) {
        return aExact - bExact;
      }
      return a.corpName.localeCompare(b.corpName, "ko");
    })
    .slice(0, 20);
}
