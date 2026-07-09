# DART Extractor

산업별 또는 사용자 지정 기업군에 대해 DART 원천 데이터를 수집하는 스크립트입니다.

## 입력 파일

`corp_codes.txt` 형식:

```txt
# one corp_code per line
00126566
00503668
00309503
```

- 빈 줄 허용
- `#` 주석 줄 허용
- corp_code는 8자리 숫자만 허용

## 수집 범위

- `statements`: 전체 재무제표 (`fnlttSinglAcntAll`)
- `major_accounts`: 주요계정 (`fnlttSinglAcnt`)
- `xbrl`: 원문 XBRL 다운로드
- `notes`: `xbrl`의 별칭. 주석이 포함된 원문 XBRL 확보용

`xbrl`은 접수번호가 필요하므로 `statements` 또는 `major_accounts`와 함께 사용해야 합니다.

## 예시

사업보고서 5개년, 연결/별도 모두, 전체 재무제표:

```bash
python3 scripts/dart/main.py \
  --corp-codes-file data/input/dart/corp_codes.txt \
  --years 5 \
  --reports annual \
  --statement-bases both \
  --scopes statements
```

사업/반기/분기 모두, 연결/별도 모두, 전체 재무제표 + XBRL:

```bash
python3 scripts/dart/main.py \
  --corp-codes-file data/input/dart/corp_codes.txt \
  --years 5 \
  --reports all \
  --statement-bases both \
  --scopes statements,xbrl
```

## 산출물

- DB: `data/workspace/dart/dart_dataset.db`
- CSV export: `data/workspace/dart/exports/`
- XBRL: `data/workspace/dart/xbrl/`
