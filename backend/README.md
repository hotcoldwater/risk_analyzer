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
