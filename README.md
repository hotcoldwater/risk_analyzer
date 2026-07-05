# Risk Analyzer

DART API 기반으로 기업 재무제표를 조회하고, 연도별 부채총계, 자본총계, 부채비율을 계산해 보여주는 MVP입니다. 감사 관점의 기본 이상징후 탐지를 붙일 수 있도록 구조를 분리했습니다.

## 핵심 기능

- 기업명으로 DART 기업 검색
- 기업개황 조회
- 분석기간별 재무제표 조회
- 계정과목 정규화
- 연도별 부채총계, 자본총계, 부채비율 표 출력
- 간단한 부채비율 추이 그래프
- 기본 위험 신호 탐지 골격 제공

## 기술 스택

- Next.js App Router
- TypeScript
- Tailwind CSS
- DART Open API
- Cloudflare 배포 가능 구조

## 로컬 실행 방법

```bash
npm install
npm run dev
```

브라우저에서 `http://localhost:3000`을 열면 됩니다.

## 환경변수 설정 방법

1. `.env.example`을 참고해 `.env.local` 파일을 생성합니다.
2. 아래 값을 설정합니다.

```env
DART_API_KEY=your_dart_api_key_here
```

주의:

- `.env.local`은 커밋하지 않습니다.
- DART API Key는 서버 API route에서만 사용됩니다.
- 클라이언트에서 DART API를 직접 호출하지 않습니다.

## DART API Key 안내

이 프로젝트는 금융감독원 전자공시시스템 Open DART API 키가 필요합니다. 키가 없으면 기업 검색과 재무제표 분석이 동작하지 않습니다.

## Cloudflare 배포 방법

이 프로젝트는 `Next.js App Router + API Route`를 사용하므로 정적 Pages 배포가 아니라 `Cloudflare Workers + OpenNext` 방식으로 배포해야 합니다.

권장 절차:

1. Cloudflare에서 Workers 기반 프로젝트를 사용합니다.
2. 환경변수 `DART_API_KEY`를 `Build Variables and Secrets` 또는 Worker 환경변수에 추가합니다.
3. 아래 명령으로 로컬 preview 또는 배포를 실행합니다.

```bash
npm run preview
npm run deploy
```

중요:

- `risk-analyzer.pages.dev` 같은 정적 Pages 배포로 연결하면 `/api/*` 서버 라우트 때문에 404가 발생할 수 있습니다.
- 이 저장소에는 `wrangler.jsonc`와 `open-next.config.ts`를 포함해 Workers 배포 구성을 추가했습니다.

## 프로젝트 구조

```text
src/
  app/
    api/
      analyze/
      search-company/
    page.tsx
  components/
    AnalysisResult.tsx
    CompanySearchForm.tsx
    FinancialTable.tsx
    RiskSummaryCard.tsx
  lib/
    analysis/
    dart/
    utils/
  types/
```

## 향후 확장 계획

- 계정과목 급변 탐지
- 순이익과 영업현금흐름 괴리 분석
- 감사위험 계정 자동 추천
- 기준점 선택 기능
- 가중평균 리스크 스코어링
- 산업 평균/중앙값 자동 계산
- Cloudflare D1/KV 캐싱

## 현재 한계

- DART 계정과목 매핑은 핵심 계정 위주로만 구현했습니다.
- 산업 평균, 동종업계 비교, 저장 기능은 포함하지 않았습니다.
- 실제 데이터 품질은 기업별 공시 형식 차이에 영향을 받을 수 있습니다.
- 연결재무제표가 없는 경우 별도재무제표 fallback을 사용하지만, 연도별 데이터 공백은 발생할 수 있습니다.
