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

  const response = await fetch(url.toString(), {
    method: "GET",
    cache: "force-cache"
  });

  if (!response.ok) {
    throw new AppError("DART API 요청 중 오류가 발생했습니다.", "DART_CORP_CODE_HTTP_ERROR", 500);
  }

  const buffer = new Uint8Array(await response.arrayBuffer());
  const unzipped = unzipSync(buffer);
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
