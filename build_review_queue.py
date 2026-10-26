import csv
from pathlib import Path

base = Path.home() / "GinneAI" / "output"
src = base / "job_evidence.csv"
dest = base / "final_review_queue.csv"

if not src.exists():
    raise SystemExit("Missing output/job_evidence.csv")

with src.open(encoding="utf-8-sig", newline="") as f:
    jobs = list(csv.DictReader(f))

queue = []

for j in jobs:
    title = j.get("title", "")
    company = j.get("company", "")
    text = " ".join([
        title,
        company,
        j.get("page_title", ""),
        j.get("bangladesh_evidence", ""),
        j.get("worldwide_evidence", ""),
        j.get("hourly_pay_evidence", ""),
        j.get("salary_evidence", ""),
    ]).lower()

    # Priority is a review recommendation, not a verified job result.
    if "canonical" in company.lower():
        priority = "EXCLUDE_FOR_NOW"
    elif "imerit" in company.lower() and "video annotation" in title.lower():
        priority = "P1 - VERIFY"
    elif "imerit" in company.lower() and "ai trainer" in title.lower():
        priority = "P1 - VERIFY"
    elif "quickmail" in company.lower():
        priority = "P2 - VERIFY"
    elif "supportyourapp" in company.lower():
        priority = "P2 - VERIFY"
    elif "ultimate marketing" in company.lower():
        priority = "P2 - VERIFY"
    elif "tier iii" in title.lower():
        priority = "LOW - EXPERIENCE GAP"
    else:
        priority = "MANUAL REVIEW"

    # Never infer eligibility or hourly pay from a keyword alone.
    country_status = "NOT CONFIRMED"
    country_evidence = j.get("bangladesh_evidence", "")
    worldwide_evidence = j.get("worldwide_evidence", "")

    if "bangladesh" in country_evidence.lower():
        country_status = "BANGLADESH TEXT FOUND - CHECK JOB-SPECIFIC CONTEXT"
    elif worldwide_evidence:
        country_status = "WORLDWIDE TEXT FOUND - CHECK EXCEPTIONS"

    pay_status = "UNKNOWN - HOURLY RATE NOT PROVEN"
    rate_evidence = j.get("hourly_pay_evidence", "")
    if rate_evidence:
        pay_status = "HOURLY KEYWORD FOUND - CHECK IT BELONGS TO THIS JOB"

    live_status = "NOT CONFIRMED"
    if j.get("closed_evidence", "").strip():
        live_status = "POSSIBLY CLOSED - MANUAL CHECK"

    queue.append({
        "priority": priority,
        "title": title,
        "company": company,
        "country_status": country_status,
        "pay_status": pay_status,
        "live_status": live_status,
        "page_check": j.get("fetch_status", ""),
        "page_title": j.get("page_title", ""),
        "application_url": j.get("final_url") or j.get("url", ""),
        "evidence_note": (
            "Review the original job-specific description. "
            "Aggregator pages may contain unrelated job listings."
        ),
    })

order = {
    "P1 - VERIFY": 0,
    "P2 - VERIFY": 1,
    "MANUAL REVIEW": 2,
    "LOW - EXPERIENCE GAP": 3,
    "EXCLUDE_FOR_NOW": 4,
}
queue.sort(key=lambda x: (order.get(x["priority"], 9), x["company"]))

fields = list(queue[0].keys()) if queue else [
    "priority", "title", "company", "application_url"
]
with dest.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(queue)

print("Final review queue:", len(queue), "leads")
print("Saved:", dest)
for i, j in enumerate(queue, 1):
    print(f"\n{i}. {j['priority']}: {j['title']} — {j['company']}")
    print("Country:", j["country_status"])
    print("Pay:", j["pay_status"])
    print("Live:", j["live_status"])
    print("Apply:", j["application_url"])

print("\nNo job is marked confirmed. Check original employer details before applying.")
