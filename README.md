# Risk Analyzer

Open DART 기반 재무제표 표준화, 서버용 데이터셋 생성, Supabase 연동 분석 서비스를 위한 저장소입니다.

현재 서비스는 두 축으로 나뉩니다.

- `frontend/`: Cloudflare Pages에 배포되는 React/Vite UI
- `backend/`: FastAPI 분석 API

백엔드는 `DATA_SOURCE=supabase`일 때 Supabase 적재 데이터를 기준으로 기업 검색, 3개년 개요, 개별 분석, 다중 분석을 제공합니다.

## 구조

```text
risk_analyzer/
  backend/                 FastAPI API
  frontend/                React/Vite UI
  scripts/dart/            선택 기업 대상 DART 원천 추출기
  scripts/pipeline/        표준화/서버DB/동기화 스크립트
  data/input/              수집 입력 파일
  data/raw/                원천 DB 및 참고 원본
  data/workspace/          실행 중간 산출물(DB/export/XBRL)
  data/processed/          표준화 산출물, 서버용 산출물
  assets/fonts/source/     원본 폰트 보관
  docs/                    문서
```

데이터 경로는 다음처럼 구분합니다.

- `data/raw/kospi/kospi_raw.db`: 원천 KOSPI 재무제표 DB
- `data/raw/reference/`: 산업분류표, 종목 보조 원본 등
- `data/input/dart/`: corp_code 입력 파일
- `data/workspace/dart/`: 맞춤 DART 추출 DB/XBRL/export
- `data/processed/standards/`: 표준화 중간 결과
- `data/processed/server/`: 서비스 업로드용 결과
- `upload/`: Supabase 반영용 최종 CSV 묶음

## API 개요

주요 엔드포인트:

- `GET /health`
- `GET /api/company-search?q=...`
- `GET /api/company-overview?company_id=...`
- `GET /api/analyses`
- `GET /api/analyze?query=...&analysis_code=...`
- `GET /api/analyze-many?query=...&analysis_codes=...`
- `GET /api/debt-ratio?query=...`

현재 프론트는 검색형 UI를 사용합니다.

- 기업명 입력 시 자동완성 검색
- 기업 선택 후 3개년 기본 흐름 표시
- 개별 분석 모달
- 다중 분석 리포트 모달

## 백엔드 실행

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

필수 환경변수:

```bash
DATA_SOURCE=supabase
SUPABASE_DATABASE_URL=postgresql://...
FRONTEND_ORIGIN=http://localhost:5173
```

`DATA_SOURCE=dart` 모드도 남아 있지만, 현재 서비스 UI와 다중 분석 흐름은 `supabase` 기준으로 맞춰져 있습니다.

## 프론트엔드 실행

```bash
cd frontend
npm install
npm run dev
```

프론트 환경변수:

```bash
VITE_API_BASE_URL=http://localhost:8000
```

## 데이터 파이프라인

원천 추출기:

```bash
python3 scripts/dart/main.py --corp-codes-file data/input/dart/corp_codes.txt --years 5 --reports annual --statement-bases both --scopes statements
```

세부 사용법은 [scripts/dart/README.md](/Users/da_vid/Projects/risk_analyzer/scripts/dart/README.md) 참고.

루트 wrapper를 그대로 써도 되고, 실제 구현은 `scripts/pipeline/` 아래에 있습니다.

```bash
python3 analyze_accounts.py
python3 normalize_accounts.py
python3 create_server_db.py
backend/.venv/bin/python sync_supabase.py
```

역할:

- `analyze_accounts.py`: 계정명 분포/중복 후보 분석
- `normalize_accounts.py`: 표준 계정 매핑 및 표준화 결과 생성
- `create_server_db.py`: 서비스용 DB/CSV 산출
- `sync_supabase.py`: SQLite 산출물을 Supabase 테이블에 반영

산업 테이블 CSV를 기준으로 Supabase를 전체 교체할 때는 아래 명령을 사용합니다.

```bash
backend/.venv/bin/python scripts/supabase/upload_csv_bundle.py --validate-only
backend/.venv/bin/python scripts/supabase/upload_csv_bundle.py --drop-all-public-tables
```

이 흐름은 `upload/` 폴더의 `companies_basic.csv`, `industry_map.csv`, 산업별 CSV를 검증한 뒤 `public` 스키마 테이블을 새로 만들고 전체 적재합니다.

## 배포

- 프론트엔드: Cloudflare Pages
- 백엔드: Render
- DB: Supabase Postgres

Render 환경변수는 최소 다음 값이 필요합니다.

```bash
DATA_SOURCE=supabase
SUPABASE_DATABASE_URL=postgresql://...
FRONTEND_ORIGIN=https://risk-analyzer.pages.dev
```

## 현재 주의사항

- 원천 DB와 표준화 DB는 아직 다시 정제 중입니다.
- 연결/별도 구분 로직과 표준화 로직은 재검증이 필요합니다.
- `data/` 아래 대용량 파일은 로컬 작업 기준이며 Git 추적 대상에서 제외합니다.
