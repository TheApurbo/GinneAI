import csv
import re
from pathlib import Path
from difflib import SequenceMatcher
from collections import defaultdict

OUT = Path("output")
SOURCE = OUT / "canonical_jobs.csv"
REPORT = OUT / "duplicate_review.csv"

def clean(value):
    value = (value or "").lower().strip()
    value = re.sub(r"https?://", "", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())

if not SOURCE.exists():
    raise SystemExit("ERROR: output/canonical_jobs.csv not found")

with SOURCE.open(encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))

groups = defaultdict(list)
for row in rows:
    company = clean(row.get("company"))
    title = clean(row.get("title"))
    if company and title:
        groups[company].append((title, row))

pairs = []
seen = set()

for company, items in groups.items():
    for i in range(len(items)):
        title_a, row_a = items[i]
        for j in range(i + 1, len(items)):
            title_b, row_b = items[j]

            score = SequenceMatcher(None, title_a, title_b).ratio()
            if title_a == title_b or score >= 0.88:
                id_a = row_a.get("job_id", "")
                id_b = row_b.get("job_id", "")
                pair_key = tuple(sorted((id_a, id_b)))

                if pair_key in seen:
                    continue
                seen.add(pair_key)

                pairs.append({
                    "similarity": round(score, 3),
                    "company": row_a.get("company", ""),
                    "title_1": row_a.get("title", ""),
                    "url_1": row_a.get("application_url", ""),
                    "job_id_1": id_a,
                    "title_2": row_b.get("title", ""),
                    "url_2": row_b.get("application_url", ""),
                    "job_id_2": id_b,
                    "review_status": "MANUAL_REVIEW_REQUIRED",
                })

fields = [
    "similarity", "company", "title_1", "url_1", "job_id_1",
    "title_2", "url_2", "job_id_2", "review_status"
]

with REPORT.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(sorted(
        pairs, key=lambda x: x["similarity"], reverse=True
    ))

print("Duplicate review report created.")
print("Input jobs:", len(rows))
print("Potential duplicate pairs:", len(pairs))
print("Report:", REPORT)
print("Original jobs preserved: YES")
print("No jobs automatically deleted or merged.")
