# Backend

FastAPI와 `dart-fss`를 이용해 DART 데이터를 조회하고 부채비율을 계산합니다.

## 실행

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

## 삼성전자 재무제표 DB 적재

서버 실행 후 아래 API로 삼성전자 재무제표를 SQLite에 저장할 수 있습니다.

```bash
curl -X POST "http://localhost:8000/api/db/samsung-financial-statements/sync"
curl "http://localhost:8000/api/db/samsung-financial-statements"
```

기본 DB 파일은 `backend/financial_statements.db`이며, `DATABASE_PATH` 환경변수로 변경할 수 있습니다.
