import csv
from pathlib import Path

OUT = Path("output")
SOURCE = OUT / "duplicate_review.csv"
DEST = OUT / "duplicate_review_classified.csv"

if not SOURCE.exists():
    raise SystemExit("ERROR: duplicate_review.csv not found")

def classify(row):
    title_a = (row.get("title_1") or "").strip().casefold()
    title_b = (row.get("title_2") or "").strip().casefold()
    url_a = (row.get("url_1") or "").strip().rstrip("/").casefold()
    url_b = (row.get("url_2") or "").strip().rstrip("/").casefold()

    if url_a and url_a == url_b:
        return "LIKELY_DUPLICATE", "Identical application URL"

    if title_a and title_a == title_b:
        return (
            "POSSIBLE_DUPLICATE",
            "Same title; distinct URLs require vacancy-level review"
        )

    return (
        "DISTINCT_OR_UNCLEAR",
        "Titles differ; do not merge without stronger evidence"
    )

with SOURCE.open(encoding="utf-8-sig", newline="") as f:
    reader = csv.DictReader(f)
    rows = list(reader)
    fields = list(reader.fieldnames or [])

for field in ["automatic_category", "classification_reason"]:
    if field not in fields:
        fields.append(field)

for row in rows:
    category, reason = classify(row)
    row["automatic_category"] = category
    row["classification_reason"] = reason

with DEST.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)

from collections import Counter
counts = Counter(r["automatic_category"] for r in rows)

print("Duplicate review classification complete.")
print("Pairs reviewed:", len(rows))
for category, count in sorted(counts.items()):
    print(f"{category}: {count}")
print("Report:", DEST)
print("Original report preserved: YES")
print("No jobs deleted or merged: YES")
print("Classification is provisional, not employer-verified.")
