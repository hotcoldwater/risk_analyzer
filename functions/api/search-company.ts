import type { PagesContext, PagesEnv } from "../_shared";
import { fail, ok } from "../_shared";
import { searchCorporationsByName } from "../../src/lib/dart/corpCode";
import { createApiError } from "../../src/lib/utils/errors";

export async function onRequestGet(context: PagesContext<PagesEnv>) {
  try {
    const url = new URL(context.request.url);
    const query = url.searchParams.get("query")?.trim() ?? "";

    if (!query) {
      throw createApiError("기업명을 입력해 주세요.", "MISSING_QUERY", 400);
    }

    const data = await searchCorporationsByName(query, context.env.DART_API_KEY);
    return ok(data);
  } catch (error) {
    return fail(error);
  }
}
