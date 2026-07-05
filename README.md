# Risk Analyzer

DART API 기반으로 기업 재무제표를 조회하고, 연도별 부채총계, 자본총계, 부채비율을 계산해 보여주는 Cloudflare Pages Functions MVP입니다.

## 핵심 기능

- 기업명으로 DART 기업 검색
- 기업개황 조회
- 분석기간별 재무제표 조회
- 계정과목 정규화
- 연도별 부채총계, 자본총계, 부채비율 표 출력
- 간단한 부채비율 추이 그래프
- 기본 위험 신호 탐지 골격 제공

## 기술 스택

- Vite
- TypeScript
- Cloudflare Pages Functions
- DART Open API

## 프로젝트 구조

```text
functions/
  api/
    analyze.ts
    search-company.ts

src/
  client/
    main.ts
  lib/
    analysis/
    dart/
    utils/
  styles/
    site.css
  types/
```

## 로컬 실행 방법

```bash
npm install
npm run dev
```

정적 프론트는 `http://localhost:5173`에서 확인할 수 있습니다.

Cloudflare Pages Functions 환경까지 같이 보려면:

```bash
npm run build
npm run pages:dev
```

## 환경변수 설정 방법

Cloudflare Pages Functions에서는 `DART_API_KEY`를 서버 환경변수로 넣어야 합니다.

로컬 개발 예시:

```env
DART_API_KEY=your_dart_api_key_here
```

Cloudflare 배포 시:

1. Pages 프로젝트 선택
2. `Settings`
3. `Variables and secrets`
4. `DART_API_KEY` 추가

주의:

- `.env*` 와 `.dev.vars*`는 커밋하지 않습니다.
- DART API Key는 Pages Functions 서버 코드에서만 사용됩니다.
- 브라우저 번들에는 포함되지 않습니다.

## DART API Key 안내

금융감독원 Open DART API 키가 필요합니다. 키가 없으면 기업 검색과 분석 API는 오류 메시지를 반환합니다.

## Cloudflare 배포 방법

이 프로젝트는 `Cloudflare Pages + Pages Functions` 기준입니다.

Pages 프로젝트 설정:

- Framework preset: `Vite`
- Build command: `npm run build`
- Build output directory: `dist`

그리고 `functions/` 디렉토리는 프로젝트 루트에 있어야 합니다. Cloudflare 공식 문서도 Pages Functions는 루트 `/functions` 디렉토리를 사용한다고 안내합니다. Sources: https://developers.cloudflare.com/pages/functions/get-started/ , https://developers.cloudflare.com/pages/functions/routing/

배포 순서:

1. GitHub 저장소 `hotcoldwater/risk_analyzer` 연결
2. Build command를 `npm run build`로 설정
3. Output directory를 `dist`로 설정
4. `DART_API_KEY` 환경변수 추가
5. Deploy

## 현재 한계

- 계정과목 매핑은 핵심 계정 중심의 1차 규칙입니다.
- 산업 평균, 동종업계 비교, 로그인, 저장 기능은 포함하지 않았습니다.
- 기업별 공시 형식 차이로 일부 계정이 누락될 수 있습니다.
- 연결재무제표가 없으면 별도재무제표로 재시도하지만 연도별 데이터 공백은 있을 수 있습니다.

## 향후 확장 계획

- 계정과목 급변 탐지 고도화
- 순이익과 영업현금흐름 괴리 분석 고도화
- 감사위험 계정 자동 추천 UI
- 기준점 선택 기능
- 가중평균 리스크 스코어링
- 산업 평균/중앙값 자동 계산
- Cloudflare D1/KV 캐싱
