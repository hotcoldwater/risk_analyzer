# DART 기반 재무제표 이상징후 및 감사위험 탐지 서비스

## PART I. 개요

이 프로젝트는 Open DART 공시 데이터를 기반으로 기업의 재무상태와 감사위험 신호를 탐지하기 위한 서비스입니다.

MVP 단계에서는 기업명 또는 기업번호를 입력하면 DART API를 통해 재무제표 데이터를 조회하고, 부채와 자본을 추출하여 부채비율을 계산합니다.

아키텍처는 다음과 같습니다.

- `frontend/`: Cloudflare Pages에 배포할 Vite + React 프론트엔드
- `backend/`: FastAPI 기반 분석 API
- `dart-fss`: 백엔드에서만 실행되는 DART 조회 라이브러리

## PART II. 데이터 출처

- Open DART API
- `dart-fss`

주의사항:

- DART API Key는 백엔드 환경변수로만 관리합니다.
- Cloudflare Pages 또는 기타 프론트엔드 환경에서는 `dart-fss`를 직접 실행하지 않습니다.

## PART III. 인터페이스

사용자는 프론트엔드에서 기업명, 기업번호, 또는 `corp_code`를 입력합니다.

프론트엔드는 다음을 수행합니다.

- 입력값 검증
- 백엔드 API 호출
- 로딩 및 에러 표시
- 부채비율 결과 카드 렌더링

## PART IV. 로직

MVP의 기본 흐름은 다음과 같습니다.

1. 사용자가 기업명 또는 기업번호를 입력합니다.
2. FastAPI 백엔드가 해당 기업을 DART에서 검색합니다.
3. 최신 재무상태표에서 부채와 자본을 추출합니다.
4. 부채비율을 계산합니다.
5. 결과를 JSON으로 반환합니다.
6. 프론트엔드가 결과를 화면에 표시합니다.

부채비율 계산식:

`부채비율 = 부채 / 자본 × 100`

출력 형식:

- `%`
- 소수점 1자리까지 표시

## PART V. 주요 기능

MVP 기능:

- 기업명 또는 기업번호 입력
- DART 기반 기업 검색
- 최신 재무상태표 조회
- 부채/자본 추출
- 부채비율 계산
- 결과 카드 출력
- 기본 캐시 처리

향후 확장 예정:

- 최근 5개년 재무제표 수집
- 계정 급변 탐지
- 순이익과 영업활동현금흐름 괴리 분석
- 감사위험 계정 추천
- 종합 리스크 점수화
- 리포트 생성

## PART VI. 방법론

MVP에서는 완전한 표준화보다 주요 상장사의 재무상태표에서 안정적으로 `부채총계`와 `자본총계`를 찾는 것을 우선합니다.

적용 기준:

- 연결재무제표 우선
- 없으면 별도재무제표 사용
- 한글/영문 계정명 후보군 기반 탐색
- 쉼표, 괄호 음수, 공백, `-` 값을 숫자로 정규화

## PART VII. UI

UI는 재무/감사 분석 대시보드 톤으로 구성합니다.

- 상단 브랜드 영역
- 검색 입력과 분석 버튼
- 핵심 지표 카드
- 부채비율 강조
- 결과 세부 카드
- 에러 및 warning 표시

상세 디자인 기준은 [docs/design-guidelines.md](/Users/da_vid/Projects/risk_analyzer/docs/design-guidelines.md)에 정리합니다.

## PART VIII. 기타사항

- 무료 배포 전제를 고려해 데이터베이스는 사용하지 않습니다.
- 기본 캐시는 서버 메모리 캐시를 사용합니다.
- 같은 기업 반복 조회 시 DART 호출을 줄이기 위해 TTL 캐시를 적용합니다.

## PART IX. 실행 방법

백엔드:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

프론트엔드:

```bash
cd frontend
npm install
npm run dev
```

테스트 예시:

```bash
curl "http://localhost:8000/health"
curl "http://localhost:8000/api/debt-ratio?query=삼성전자"
```
