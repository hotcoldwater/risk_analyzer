import { NextRequest, NextResponse } from "next/server";
import { searchCorporationsByName } from "@/lib/dart/corpCode";
import { createApiError, toKoreanErrorMessage } from "@/lib/utils/errors";

export async function GET(request: NextRequest) {
  try {
    const query = request.nextUrl.searchParams.get("query")?.trim() ?? "";

    if (!query) {
      throw createApiError("기업명을 입력해 주세요.", "MISSING_QUERY", 400);
    }

    const data = await searchCorporationsByName(query);
    return NextResponse.json({ success: true, data });
  } catch (error) {
    const message = toKoreanErrorMessage(error);
    return NextResponse.json({ success: false, error: message }, { status: 400 });
  }
}
