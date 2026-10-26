import csv
import html
import json
import re
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "output/himalayas_cache.json"
OUT = ROOT / "output/himalayas_jobs.csv"
CACHE_SECONDS = 12 * 60 * 60

QUERIES = [
    "technical support",
    "customer support",
    "AI trainer",
    "Linux support",
]

def clean(value):
    value = re.sub(r"<[^>]*>", " ", str(value or ""))
    return re.sub(r"\s+", " ", html.unescape(value)).strip()

def get_jobs():
    if CACHE.exists():
        try:
            data = json.loads(CACHE.read_text(encoding="utf-8"))
            if time.time() - data["fetched_at"] < CACHE_SECONDS:
                print("Using cached Himalayas results.")
                return data["jobs"]
        except (ValueError, KeyError, OSError):
            pass

    jobs = []
    seen = set()

    for query in QUERIES:
        params = urlencode({
            "q": query,
            "sort": "recent",
            "page": 1
        })
        url = "https://himalayas.app/jobs/api/search?" + params
        request = Request(url, headers={
            "User-Agent": "GinneAI-Personal-JobSearch/1.0",
            "Accept": "application/json"
        })

        try:
            with urlopen(request, timeout=25) as response:
                data = json.loads(response.read().decode("utf-8"))

            batch = data.get("jobs", [])
            for job in batch:
                key = job.get("guid") or job.get("applicationLink")
                if key and key not in seen:
                    seen.add(key)
                    jobs.append(job)

            print(f"{query}: {len(batch)} listings")
        except Exception as exc:
            print(f"{query}: fetch failed - {str(exc)[:120]}")

    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps({
        "fetched_at": time.time(),
        "jobs": jobs
    }, ensure_ascii=False), encoding="utf-8")
    return jobs

def evaluate(job):
    title = clean(job.get("title"))
    company = clean(job.get("companyName"))
    description = clean(job.get("description") or job.get("excerpt"))
    link = str(job.get("applicationLink") or "").strip()
    period = str(job.get("salaryPeriod") or "annual").lower()
    currency = str(job.get("currency") or "").upper()
    minimum = job.get("minSalary")
    maximum = job.get("maxSalary")
    restrictions = job.get("locationRestrictions") or []
    timezones = job.get("timezoneRestrictions") or []

    if not link.startswith("https://"):
        return "REVIEW", "Application link needs checking"

    if restrictions:
        restriction_text = " ".join(map(str, restrictions)).lower()
        if not any(x in restriction_text for x in ("bd", "bangladesh")):
            return "REVIEW", "Country restriction: " + ", ".join(map(str, restrictions))
        country_status = "Bangladesh listed"
    elif timezones:
        country_status = "Timezone restrictions need checking"
    else:
        country_status = "No country restriction listed; verify employer"

    if period != "hourly":
        return "REVIEW", f"Pay period is {period}, not confirmed hourly"

    if currency != "USD":
        return "REVIEW", f"Hourly currency is {currency or 'unknown'}"

    try:
        if minimum is None or float(minimum) < 10:
            return "REVIEW", "USD $10/hour minimum not confirmed"
    except (TypeError, ValueError):
        return "REVIEW", "Hourly rate not confirmed"

    text = (title + " " + description).lower()
    relevant = any(term in text for term in (
        "technical support", "customer support", "help desk",
        "service desk", "linux", "troubleshooting",
        "ai trainer", "ai training", "data annotation"
    ))

    if not relevant:
        return "REVIEW", "Role relevance needs checking"

    return "REVIEW", country_status + "; verify original listing and requirements"

def main():
    jobs = get_jobs()
    rows = []

    for job in jobs:
        status, reason = evaluate(job)
        restrictions = job.get("locationRestrictions") or []
        rows.append({
            "title": clean(job.get("title")),
            "company": clean(job.get("companyName")),
            "employment_type": clean(job.get("employmentType")),
            "country_restrictions": ", ".join(map(str, restrictions)),
            "salary_min": job.get("minSalary", ""),
            "salary_max": job.get("maxSalary", ""),
            "salary_period": job.get("salaryPeriod", "annual"),
            "currency": job.get("currency", ""),
            "status": status,
            "reason": reason,
            "apply_url": job.get("applicationLink", ""),
            "source": "Himalayas",
            "source_url": "https://himalayas.app"
        })

    fields = list(rows[0].keys()) if rows else [
        "title", "company", "employment_type",
        "country_restrictions", "salary_min", "salary_max",
        "salary_period", "currency", "status", "reason",
        "apply_url", "source", "source_url"
    ]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nUnique listings: {len(rows)}")
    print(f"Saved: {OUT.relative_to(ROOT)}")
    print("Source: Himalayas — https://himalayas.app")

    for job in rows[:10]:
        print(f"\n[{job['status']}] {job['title']} — {job['company']}")
        print("Pay:", job["salary_min"], "-", job["salary_max"],
              job["currency"], "/", job["salary_period"])
        print("Check:", job["reason"])
        print("Apply:", job["apply_url"])

if __name__ == "__main__":
    main()
