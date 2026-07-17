"""Read-only quality report for a CSV upload bundle.

This is deliberately separate from the uploader: it reports all known blockers
in one run and never changes a CSV file or a database.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BUNDLE_DIR = PROJECT_ROOT / "look"


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        return reader.fieldnames or [], list(reader)


def clean_identifier(value: str | None) -> str:
    return (value or "").strip().strip('"').strip()


def bundle_paths(bundle_dir: Path) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for path in bundle_dir.glob("*.csv"):
        name = path.stem.split(" - ")[-1].lower().replace(" ", "_")
        paths[name] = path
    return paths


def inspect(bundle_dir: Path) -> dict[str, object]:
    paths = bundle_paths(bundle_dir)
    issues: list[dict[str, object]] = []
    required = {"companies_basic", "industry_map"}
    for name in sorted(required - paths.keys()):
        issues.append({"severity": "error", "code": "missing_required_file", "detail": name})
    if required - paths.keys():
        return {"bundle": str(bundle_dir), "status": "blocked", "issues": issues}

    _, companies = read_rows(paths["companies_basic"])
    _, industry_map = read_rows(paths["industry_map"])
    company_codes = {clean_identifier(row.get("corp_code")) for row in companies}
    duplicate_companies = [code for code, count in Counter(clean_identifier(row.get("corp_code")) for row in companies).items() if count > 1]
    if duplicate_companies:
        issues.append({"severity": "error", "code": "duplicate_company_master", "corp_codes": sorted(duplicate_companies)})

    map_by_industry: dict[str, set[str]] = {}
    for row in industry_map:
        industry = (row.get("industry_id") or "").strip()
        map_by_industry.setdefault(industry, set()).add(clean_identifier(row.get("corp_code")))

    industries: dict[str, object] = {}
    for industry_id, path in sorted(paths.items()):
        if industry_id in required:
            continue
        headers, rows = read_rows(path)
        codes = {clean_identifier(row.get("corp_code")) for row in rows}
        missing_from_master = sorted(codes - company_codes)
        missing_from_map = sorted(codes - map_by_industry.get(industry_id, set()))
        natural_keys = Counter(
            (
                clean_identifier(row.get("corp_code")),
                row.get("year", "").strip(),
                row.get("fs_div", "").strip(),
                row.get("sj_div", "").strip(),
                row.get("account_name", "").strip(),
            )
            for row in rows
        )
        duplicates = sum(count - 1 for count in natural_keys.values() if count > 1)
        industries[industry_id] = {
            "file": path.name,
            "rows": len(rows),
            "companies": len(codes),
            "years": sorted({row.get("year", "").strip() for row in rows}),
            "headers": headers,
            "missing_from_company_master": missing_from_master,
            "missing_from_industry_map": missing_from_map,
            "duplicate_financial_facts": duplicates,
        }
        if missing_from_master:
            issues.append({"severity": "error", "code": "missing_company_master", "industry": industry_id, "count": len(missing_from_master)})
        if missing_from_map:
            issues.append({"severity": "error", "code": "missing_industry_mapping", "industry": industry_id, "count": len(missing_from_map)})
        if duplicates:
            issues.append({"severity": "error", "code": "duplicate_financial_fact", "industry": industry_id, "count": duplicates})

    return {
        "bundle": str(bundle_dir),
        "status": "blocked" if any(issue["severity"] == "error" for issue in issues) else "ready",
        "company_master_rows": len(companies),
        "company_master_unique_codes": len(company_codes),
        "industry_membership_rows": len(industry_map),
        "industries": industries,
        "issues": issues,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a read-only CSV bundle quality report.")
    parser.add_argument("--bundle-dir", type=Path, default=DEFAULT_BUNDLE_DIR)
    parser.add_argument("--output", type=Path, help="Optional JSON report output path.")
    args = parser.parse_args()
    report = inspect(args.bundle_dir)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
        print(f"Quality report written to {args.output}")
    print(rendered)


if __name__ == "__main__":
    main()
