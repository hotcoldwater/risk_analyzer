# Supabase Upload Bundle

`upload/` 폴더의 CSV 묶음을 검증한 뒤 Supabase에 전체 교체 방식으로 적재한다.

기본 파일:

- `Samil Project DB - companies_basic.csv`
- `Samil Project DB - industry_map.csv`
- 산업별 CSV (`defense.csv`, `construction.csv`, `semiconductor.csv` 등)

검증:

- `corp_code`는 8자리 숫자
- `stock_code`는 6자리 영숫자
- 산업 테이블의 기업 정보가 `companies_basic.csv`와 일치하는지 확인
- 금액 문자열(`47,812,373,057`)을 숫자로 변환 가능해야 함

사용 예시:

```bash
backend/.venv/bin/python scripts/supabase/upload_csv_bundle.py --validate-only
backend/.venv/bin/python scripts/supabase/upload_csv_bundle.py
backend/.venv/bin/python scripts/supabase/upload_csv_bundle.py --drop-all-public-tables
```

`--drop-all-public-tables`를 사용하면 `public` 스키마의 기존 테이블을 전부 삭제한 뒤 새 테이블을 만든다.
