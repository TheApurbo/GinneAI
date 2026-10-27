import csv
from pathlib import Path

BASE = Path.home() / "GinneAI"
OUT = BASE / "output"

def read_csv(path):
    if not path.exists():
        raise SystemExit(f"Missing file: {path}")
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def write_csv(path, rows, fields=None):
    if fields is None:
        fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

def key(row):
    return (
        row.get("title", "").strip().casefold(),
        row.get("company", "").strip().casefold()
    )

verified = read_csv(OUT / "verification_results.csv")
old_evidence = read_csv(OUT / "job_evidence.csv")

evidence_by_key = {}
for row in old_evidence:
    evidence_by_key.setdefault(key(row), []).append(row)

merged = []
for original in verified:
    matches = evidence_by_key.get(key(original), [])
    evidence = matches.pop(0) if matches else {}

    # Keep all original verification metadata; restore extracted evidence fields.
    row = dict(original)
    for field, value in evidence.items():
        if field not in row or value not in ("", None):
            row[field] = value

    row["source"] = original.get("source", "")
    row["source_url"] = original.get("source_url", "")
    row["apply_url"] = original.get("apply_url", "")
    row["url"] = evidence.get("url") or original.get("final_url") or original.get("apply_url", "")
    row["final_url"] = evidence.get("final_url") or original.get("final_url", "")
    row["location"] = original.get("location", "")
    row["eligible_countries"] = original.get("eligible_countries", "")
    row["pay_min"] = original.get("pay_min", "")
    row["pay_max"] = original.get("pay_max", "")
    row["currency"] = original.get("currency", "")
    row["salary_period"] = original.get("salary_period", "")
    merged.append(row)

write_csv(OUT / "job_evidence.csv", merged)

queue = []
for row in merged:
    title = row.get("title", "")
    company = row.get("company", "")
    title_l = title.lower()
    company_l = company.lower()

    if "canonical" in company_l:
        priority = "EXCLUDE_FOR_NOW"
    elif "imerit" in company_l and ("ai trainer" in title_l or "video annotation" in title_l):
        priority = "P1 - VERIFY"
    elif any(name in company_l for name in ("quickmail", "supportyourapp", "ultimate marketing")):
        priority = "P2 - VERIFY"
    elif "tier iii" in title_l:
        priority = "LOW - EXPERIENCE GAP"
    else:
        priority = "MANUAL REVIEW"

    bangladesh_evidence = row.get("bangladesh_evidence", "")
    worldwide_evidence = row.get("worldwide_evidence", "")
    hourly_evidence = row.get("hourly_pay_evidence", "")
    closed_evidence = row.get("closed_evidence", "")
    fetch_status = row.get("fetch_status", "")

    if bangladesh_evidence:
        country_status = "BANGLADESH TEXT FOUND - CHECK JOB-SPECIFIC CONTEXT"
    elif worldwide_evidence:
        country_status = "WORLDWIDE TEXT FOUND - CHECK EXCEPTIONS"
    else:
        country_status = "NOT CONFIRMED"

    pay_status = (
        "HOURLY KEYWORD FOUND - CHECK JOB-SPECIFIC RATE"
        if hourly_evidence else
        "UNKNOWN - HOURLY RATE NOT PROVEN"
    )

    if closed_evidence:
        live_status = "POSSIBLY CLOSED - MANUAL CHECK"
    elif fetch_status.startswith("HTTP_"):
        live_status = "PAGE REACHED - VACANCY NOT CONFIRMED"
    else:
        live_status = "NOT CONFIRMED"

    queue.append({
        "priority": priority,
        "title": title,
        "company": company,
        "source": row.get("source", ""),
        "source_url": row.get("source_url", ""),
        "application_url": row.get("final_url") or row.get("apply_url") or row.get("url", ""),
        "location": row.get("location", ""),
        "eligible_countries": row.get("eligible_countries", ""),
        "country_status": country_status,
        "bangladesh_evidence": bangladesh_evidence,
        "worldwide_evidence": worldwide_evidence,
        "pay_min": row.get("pay_min", ""),
        "pay_max": row.get("pay_max", ""),
        "currency": row.get("currency", ""),
        "salary_period": row.get("salary_period", ""),
        "pay_status": pay_status,
        "hourly_pay_evidence": hourly_evidence,
        "salary_evidence": row.get("salary_evidence", ""),
        "live_status": live_status,
        "fetch_status": fetch_status,
        "page_title": row.get("page_title", ""),
        "closed_evidence": closed_evidence,
        "review_hint": row.get("review_hint", "MANUAL_REVIEW"),
        "bangladesh_eligibility_verified": "NO",
        "hourly_rate_10_usd_or_more_verified": "NO",
        "vacancy_open_verified": "NO",
        "final_decision": "NEEDS_VERIFICATION",
        "evidence_note": "Extracted page text is a clue, not proof. Check the job-specific employer listing.",
    })

priority_order = {
    "P1 - VERIFY": 0,
    "P2 - VERIFY": 1,
    "MANUAL REVIEW": 2,
    "LOW - EXPERIENCE GAP": 3,
    "EXCLUDE_FOR_NOW": 4,
}
queue.sort(key=lambda r: (
    priority_order.get(r["priority"], 9),
    r["company"].lower(),
    r["title"].lower()
))
write_csv(OUT / "final_review_queue.csv", queue)

print("Schema repair complete.")
print("Verification rows:", len(verified))
print("Evidence rows:", len(merged))
print("Review queue rows:", len(queue))
print("Restored source, location, pay metadata and original verification fields.")
print("No new vacancy, eligibility or pay claim has been marked verified.")
