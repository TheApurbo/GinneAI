import csv
from pathlib import Path
from collections import Counter

ROOT = Path.home() / "GinneAI"
OUT = ROOT / "output"

FILES = [
    "multi_source_jobs.csv",
    "priority_leads.csv",
    "verification_results.csv",
    "job_evidence.csv",
    "final_review_queue.csv",
    "ranked_job_matches.csv",
]

ALIASES = {
    "apply_url": ["apply_url", "application_url", "url"],
    "country": [
        "eligible_countries", "country_restrictions",
        "country_status", "bangladesh_check"
    ],
    "pay": [
        "pay_min", "pay_min_usd", "salary_min",
        "hourly_pay_evidence", "pay_status", "pay_check"
    ],
    "status": [
        "status", "verification_status", "live_status",
        "final_decision", "review_hint"
    ],
    "source": ["source", "source_url"],
}

print("=" * 60)
print("GINNE AI — READ-ONLY PIPELINE AUDIT")
print("=" * 60)

all_rows = {}
all_fields = {}

for filename in FILES:
    path = OUT / filename
    print(f"\n--- {filename} ---")

    if not path.exists():
        print("MISSING FILE")
        continue

    try:
        with path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            fields = reader.fieldnames or []
            rows = list(reader)

        all_rows[filename] = rows
        all_fields[filename] = fields

        print("Rows:", len(rows))
        print("Columns:", len(fields))

        for concept, aliases in ALIASES.items():
            found = [name for name in aliases if name in fields]
            print(f"{concept}: {', '.join(found) if found else 'MISSING'}")

        if "apply_url" in fields or "application_url" in fields or "url" in fields:
            url_col = next(
                name for name in ["apply_url", "application_url", "url"]
                if name in fields
            )
            urls = [
                (row.get(url_col) or "").strip().lower()
                for row in rows
            ]
            nonempty = [u for u in urls if u]
            print("Missing URLs:", len(urls) - len(nonempty))
            print("Duplicate URLs in this file:",
                  len(nonempty) - len(set(nonempty)))

        title_col = "title" if "title" in fields else None
        company_col = "company" if "company" in fields else None

        if title_col and company_col:
            keys = [
                (
                    (r.get(title_col) or "").strip().lower(),
                    (r.get(company_col) or "").strip().lower()
                )
                for r in rows
            ]
            counts = Counter(keys)
            duplicate_pairs = sum(n - 1 for n in counts.values() if n > 1)
            print("Repeated title+company pairs:", duplicate_pairs)

    except Exception as exc:
        print("READ ERROR:", exc)

print("\n" + "=" * 60)
print("CROSS-FILE FIELD CONSISTENCY")
print("=" * 60)

for filename, fields in all_fields.items():
    print(f"\n{filename}")
    for concept, aliases in ALIASES.items():
        found = [x for x in aliases if x in fields]
        if found:
            print(f"  {concept} -> {found[0]}")
        else:
            print(f"  {concept} -> NOT AVAILABLE")

print("\n" + "=" * 60)
print("AUDIT COMPLETE — NO FILES MODIFIED")
print("=" * 60)
