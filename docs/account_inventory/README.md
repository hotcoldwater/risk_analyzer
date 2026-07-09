# KOSPI 재무제표 계정과목 인벤토리

원본 DB `data/raw/kospi/kospi_raw.db`의 `financial_statements.account_nm`을 재무제표 종류(`sj_nm`)별로 분리한 문서 모음이다.

## 문서 목록

- [재무상태표 계정과목](./balance_sheet_accounts.md): 3,131개
- [손익계산서 계정과목](./income_statement_accounts.md): 783개
- [포괄손익계산서 계정과목](./comprehensive_income_accounts.md): 4,850개
- [현금흐름표 계정과목](./cash_flow_accounts.md): 11,788개
- [자본변동표 계정과목](./statement_of_changes_in_equity_accounts.md): 4,186개

## 메모

- 각 문서는 `DISTINCT account_nm` 기준으로 정렬되어 있다.
- 동일 의미 계정이라도 공백, 기호, 번호, 괄호, 표기 방식 차이로 별도 항목으로 남아 있다.
- 정규화 작업 전 사람이 직접 검토하기 위한 인벤토리 문서다.
