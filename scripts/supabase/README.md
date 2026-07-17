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
- 최신 번들의 수익인식 메타데이터(`수익인식기준`, `수익인식 코드`, `분류`)를 지원
- 지수 표기 금액과 스프레드시트에서 남은 식별자 따옴표를 정규화
- 기업·연도·재무제표·계정 기준의 중복 재무 사실을 차단

품질 리포트(읽기 전용):

```bash
python3 scripts/supabase/inspect_csv_bundle.py --bundle-dir look
```

이 명령은 원본이나 DB를 변경하지 않고 기업 마스터, 산업맵, 중복 사실, 기간 및 누락 참조를 JSON으로 보고한다.

승인된 최신 번들에서 기업 마스터의 기준일이 일부 비어 있고 산업 그룹이 아직 확정되지 않은 경우에만 다음 명시 옵션을 사용한다. 이 방식은 원본 CSV를 바꾸지 않으며, 생성된 `UNCLASSIFIED` 기업은 A/B/C 비교군에 포함되지 않는다.

```bash
backend/.venv/bin/python scripts/supabase/upload_csv_bundle.py \
  --upload-dir look \
  --default-updated-at 2026-07-11 \
  --auto-map-unclassified-industries \
  --reconcile-stock-codes \
  --validate-only
```

`--reconcile-stock-codes`는 법인코드와 기업명이 일치하고 산업별 재무 CSV 전체가 하나의 종목코드로 일관된 경우에만, 적재 중인 마스터 값을 해당 코드로 교정한다. 원본 CSV는 수정하지 않으며 변경 목록을 출력한다.

사용 예시:

```bash
backend/.venv/bin/python scripts/supabase/upload_csv_bundle.py --validate-only
backend/.venv/bin/python scripts/supabase/upload_csv_bundle.py
backend/.venv/bin/python scripts/supabase/upload_csv_bundle.py --drop-all-public-tables
```

`--drop-all-public-tables`를 사용하면 `public` 스키마의 기존 테이블을 전부 삭제한 뒤 새 테이블을 만든다.
