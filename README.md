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

이 프로젝트는 Next.js 기반이며 Cloudflare Pages 또는 Workers 배포를 전제로 작성했습니다.

권장 절차:

1. Cloudflare에서 Next.js 배포용 프로젝트를 생성합니다.
2. 빌드 명령을 `npm run build`로 설정합니다.
3. `DART_API_KEY` 환경변수를 Cloudflare 프로젝트 환경변수에 추가합니다.
4. 서버사이드 API route가 실행되는 배포 모드를 사용합니다.

실제 배포 시에는 팀 표준에 맞춰 OpenNext Cloudflare 어댑터 또는 Cloudflare의 최신 Next.js 지원 방식을 선택하면 됩니다.

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
