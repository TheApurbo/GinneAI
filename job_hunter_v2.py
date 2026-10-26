import csv
import html
import json
import re
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output/job_hunter_v2.csv"
CACHE = ROOT / "output/job_hunter_v2_cache.json"
CACHE_AGE = 24 * 60 * 60

QUERIES = [
    "technical support",
    "IT support",
    "help desk",
    "service desk",
    "customer support",
    "email support",
    "chat support",
    "technical customer service",
    "Linux support",
    "cloud support",
    "AI evaluator",
    "AI trainer",
    "data annotator",
    "quality assurance tester",
    "junior technical support",
    "IT operations",

    "data annotation",
    "AI data trainer",
    "AI response evaluator",
    "AI safety evaluator",
    "engineering AI evaluator",
    "electronics engineering AI",
    "PCB design AI training",
    "KiCad task specialist",
    "AutoCAD task creation",
    "CAD data annotation",
    "Ubuntu Linux AI trainer",
    "Linux workflow recording",
    "technical drawing AI training",
    "computer vision annotation",
    "image annotation",
    "video annotation",
    "Bengali AI trainer",
]

ROLE_TERMS = [
    "support", "help desk", "helpdesk", "service desk",
    "customer service", "customer experience", "linux",
    "cloud", "technical", "ai trainer", "ai evaluator",
    "data annotation", "data annotator", "quality assurance",
    "qa tester", "it operations", "troubleshooting",
    "email support", "chat support",
]

SENIOR_TERMS = [
    "senior", "sr.", "lead ", "principal", "director",
    "head of ", "vice president", "vp ", "manager",
    "staff engineer", "architect",
]

def clean(value):
    value = re.sub(r"<[^>]*>", " ", str(value or ""))
    return re.sub(r"\s+", " ", html.unescape(value)).strip()

def values(items):
    if not isinstance(items, list):
        return str(items or "")
    return ", ".join(
        str(x.get("name", x.get("code", x)))
        if isinstance(x, dict) else str(x)
        for x in items
    )

def fetch_jobs():
    if CACHE.exists():
        try:
            saved = json.loads(CACHE.read_text(encoding="utf-8"))
            if time.time() - saved["fetched_at"] < CACHE_AGE:
                print("Using cached results.")
                return saved["jobs"]
        except (ValueError, KeyError, OSError):
            pass

    found = {}
    searches = [(q, {"worldwide": "true"}) for q in QUERIES]
    searches += [(q, {"country": "Bangladesh"}) for q in QUERIES]

    for query, filters in searches:
        params = {"q": query, "sort": "recent", **filters}
        url = "https://himalayas.app/jobs/api/search?" + urlencode(params)
        request = Request(url, headers={
            "User-Agent": "GinneAI-Personal-JobSearch/2.0",
            "Accept": "application/json",
        })

        try:
            with urlopen(request, timeout=25) as response:
                data = json.loads(response.read().decode("utf-8"))

            for job in data.get("jobs", []):
                key = job.get("guid") or job.get("applicationLink")
                if key:
                    found[key] = job

            print(f"{query} [{filters}]: "
                  f"{len(data.get('jobs', []))} results")
        except Exception as exc:
            print(f"Search failed ({query}): {str(exc)[:100]}")

        time.sleep(0.25)

    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps({
        "fetched_at": time.time(),
        "jobs": list(found.values()),
    }, ensure_ascii=False), encoding="utf-8")

    return list(found.values())

def evaluate(job):
    title = clean(job.get("title"))
    company = clean(job.get("companyName"))
    description = clean(job.get("description") or job.get("excerpt"))
    text = (title + " " + description).lower()

    link = str(job.get("applicationLink") or "").strip()
    period = str(job.get("salaryPeriod") or "annual").lower()
    currency = str(job.get("currency") or "").upper()
    restrictions = job.get("locationRestrictions") or []
    timezones = job.get("timezoneRestrictions") or []

    country_text = values(restrictions).lower()
    try:
        timezone_values = [float(str(x).replace("UTC", "").replace("+", ""))
                           for x in timezones]
    except (ValueError, TypeError):
        timezone_values = []

    if not link.startswith("https://"):
        return "REJECT", "No valid HTTPS application link"

    if any(term in title.lower() for term in SENIOR_TERMS):
        return "REJECT", "Senior/leadership title; not the current target"

    if any(term in text for term in [
        "commission only", "unpaid position", "unpaid internship"
    ]):
        return "REJECT", "Unpaid or commission-only work"

    relevant = any(term in text for term in ROLE_TERMS)
    if not relevant:
        return "REJECT", "Not relevant to the current job targets"

    if restrictions and "bangladesh" not in country_text and " bd" not in country_text:
        location = "REJECT"
        location_note = "Country restriction: " + values(restrictions)
    elif timezones and not any(abs(x - 6) < 0.01 for x in timezone_values):
        location = "REJECT"
        location_note = "Timezone restriction may exclude Bangladesh: " + values(timezones)
    else:
        location = "POTENTIAL"
        location_note = (
            "Bangladesh listed; verify employer"
            if restrictions else
            "No country restriction listed; verify employer"
        )

    salary_min = job.get("minSalary")
    try:
        pay = float(salary_min) if salary_min is not None else None
    except (ValueError, TypeError):
        pay = None

    if period == "hourly" and currency == "USD" and pay is not None and pay < 10:
        return "REJECT", f"Below $10/hour; {location_note}"

    if period != "hourly" or currency != "USD" or pay is None:
        pay_note = "Hourly USD rate of at least $10 is not confirmed"
        status = "POTENTIAL" if location != "REJECT" else "REJECT"
        return status, f"{location_note}; {pay_note}"

    if location == "REJECT":
        return "REJECT", location_note

    # A listing is never declared fully verified from search metadata alone.
    return "POTENTIAL", (
        f"{location_note}; listed pay starts at ${pay}/hour; "
        "verify role requirements and original listing"
    )

def main():
    jobs = fetch_jobs()
    rows = []

    for job in jobs:
        status, reason = evaluate(job)
        rows.append({
            "title": clean(job.get("title")),
            "company": clean(job.get("companyName")),
            "seniority": values(job.get("seniority") or []),
            "employment_type": clean(job.get("employmentType")),
            "salary_min": job.get("minSalary", ""),
            "salary_max": job.get("maxSalary", ""),
            "currency": job.get("currency", ""),
            "salary_period": job.get("salaryPeriod", "annual"),
            "country_restrictions": values(job.get("locationRestrictions") or []),
            "timezone_restrictions": values(job.get("timezoneRestrictions") or []),
            "status": status,
            "reason": reason,
            "apply_url": job.get("applicationLink", ""),
            "source": "Himalayas",
        })

    fields = list(rows[0].keys()) if rows else [
        "title", "company", "seniority", "employment_type",
        "salary_min", "salary_max", "currency", "salary_period",
        "country_restrictions", "timezone_restrictions",
        "status", "reason", "apply_url", "source"
    ]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    counts = {s: sum(r["status"] == s for r in rows)
              for s in ("POTENTIAL", "REJECT", "MATCH")}

    print(f"\nUnique listings: {len(rows)}")
    print("POTENTIAL:", counts["POTENTIAL"])
    print("REJECT:", counts["REJECT"])
    print("MATCH:", counts["MATCH"])
    print("Saved:", OUT)

    potential = [r for r in rows if r["status"] == "POTENTIAL"]
    for j in potential[:20]:
        print(f"\n[POTENTIAL] {j['title']} — {j['company']}")
        print("Pay:", j["salary_min"], "-", j["salary_max"],
              j["currency"], "/", j["salary_period"])
        print("Check:", j["reason"])
        print("Apply:", j["apply_url"])

    print("\nSource: Himalayas — https://himalayas.app")

if __name__ == "__main__":
    main()
