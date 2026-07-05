# Risk Analyzer

DART 재무제표를 조회해 부채총계, 자본총계, 부채비율을 분석하는 MVP입니다. 프론트는 Cloudflare Pages 정적 사이트로 배포하고, DART 호출은 Python `FastAPI + dart-fss` 백엔드에서 처리합니다.

## 구조

- 프론트: Vite 정적 웹앱
- 백엔드: FastAPI
- DART 연동: `dart-fss`
- 프론트 배포: Cloudflare Pages
- 백엔드 배포: Render Free Web Service

## 프로젝트 구조

```text
backend/
  app/
    main.py
  requirements.txt

src/
  client/
    main.ts
  lib/
    utils/
  styles/
    site.css
  types/

render.yaml
```

## 동작 방식

1. 사용자가 Cloudflare Pages 프론트에서 기업명을 검색합니다.
2. 프론트가 FastAPI 백엔드의 `/search-company`를 호출합니다.
3. FastAPI가 `dart-fss`로 기업 목록을 조회합니다.
4. 사용자가 분석을 실행하면 프론트가 `/analyze`를 호출합니다.
5. FastAPI가 `dart-fss`로 재무제표를 불러와 가공하고 결과를 반환합니다.

## 로컬 실행

프론트:

```bash
npm install
npm run dev
```

백엔드:

```bash
python3 -m pip install -r backend/requirements.txt
DART_API_KEY=your_dart_api_key_here npm run backend:dev
```

프론트가 로컬 백엔드를 보게 하려면 `.env.local` 파일을 만들고 아래를 넣습니다.

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## 환경변수

프론트 빌드 환경변수:

```env
VITE_API_BASE_URL=https://your-backend.onrender.com
```

백엔드 환경변수:

```env
DART_API_KEY=your_dart_api_key_here
```

주의:

- `VITE_API_BASE_URL`은 프론트가 호출할 백엔드 URL입니다.
- `DART_API_KEY`는 FastAPI 백엔드에만 넣습니다.
- DART 키를 Cloudflare Pages에 넣지 않습니다.

## Cloudflare Pages 배포

이 저장소의 프론트를 Cloudflare Pages에 배포합니다.

설정:

- Framework preset: `Vite` 또는 `React (Vite)`
- Build command: `npm run build`
- Build output directory: `dist`
- Environment variable: `VITE_API_BASE_URL=https://your-backend.onrender.com`

## Render 배포

이 저장소의 `backend/`를 Render Free Web Service로 배포합니다.

설정:

- Environment: `Python`
- Root Directory: `backend`
- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Environment Variable: `DART_API_KEY=your_dart_api_key_here`

`render.yaml`도 포함되어 있습니다.

## 현재 한계

- `dart-fss`의 `web` 데이터셋 기반이라 기업별 표 구조 차이의 영향을 받을 수 있습니다.
- 산업 평균, 동종업계 비교, 저장 기능은 아직 없습니다.
- 보고서 유형은 `annual`, `half`, `quarter` 수준으로 매핑합니다.

## 향후 확장

- 계정 급변 탐지 정교화
- 순이익과 영업현금흐름 괴리 분석 고도화
- 감사위험 계정 추천 UI
- 기업/조회 결과 캐싱
- 산업 비교와 점수화
