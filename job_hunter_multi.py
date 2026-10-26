import csv
import json
import re
import time
import html
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from datetime import datetime, timezone

OUT = Path("output")
OUT.mkdir(exist_ok=True)
DEST = OUT / "multi_source_jobs.csv"

HEADERS = {
    "User-Agent": "GinneAIJobResearch/1.0 (personal job discovery)",
    "Accept": "application/json, application/rss+xml, application/xml, text/xml"
}

ROLE_TERMS = [
    "data annotat", "data label", "ai trainer", "ai evaluator",
    "ai training", "ai safety", "llm evaluator", "response evaluator",
    "technical support", "it support", "help desk", "service desk",
    "linux support", "cloud support", "customer support",
    "qa tester", "quality assurance", "software tester",
    "electronics", "avionics", "pcb", "kicad", "autocad",
    "cad ", "technical drawing", "computer vision",
    "image annotation", "video annotation", "bengali",
    "python", "junior engineer", "technical writer",
    "engineering"
]

FIELDS = [
    "title", "company", "location", "remote", "eligible_countries",
    "pay_type", "pay_min", "pay_max", "currency", "salary_period",
    "employment_type", "published", "description", "apply_url",
    "source", "source_url", "relevance_score", "status",
    "verification_note", "collected_at"
]

def get_json(url):
    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8", "replace"))

def clean(value):
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)
    value = re.sub(r"<[^>]+>", " ", str(value))
    return re.sub(r"\s+", " ", html.unescape(value)).strip()

def first(obj, *keys):
    for key in keys:
        value = obj.get(key)
        if value not in (None, "", [], {}):
            return value
    return ""

def make_job(title, company, description, url, source, **extra):
    title = clean(title)
    description = clean(description)
    url = clean(url)

    if not title or not url.startswith("https://"):
        return None

    searchable = (title + " " + description).lower()
    matched = [term for term in ROLE_TERMS if term in searchable]
    if not matched:
        return None

    title_lower = title.lower()
    title_hits = sum(1 for term in ROLE_TERMS if term in title_lower)
    score = min(100, len(set(matched)) * 8 + title_hits * 12)

    salary_min = extra.get("pay_min", "")
    salary_max = extra.get("pay_max", "")
    currency = clean(extra.get("currency", ""))
    period = clean(extra.get("salary_period", ""))
    pay_type = "Hourly" if period.lower() in ("hour", "hourly", "per hour") else (
        "Monthly" if period.lower() in ("month", "monthly", "per month") else
        "Not stated"
    )

    return {
        "title": title,
        "company": clean(company),
        "location": clean(extra.get("location", "")),
        "remote": clean(extra.get("remote", "")),
        "eligible_countries": clean(extra.get("eligible_countries", "")),
        "pay_type": pay_type,
        "pay_min": clean(salary_min),
        "pay_max": clean(salary_max),
        "currency": currency,
        "salary_period": period,
        "employment_type": clean(extra.get("employment_type", "")),
        "published": clean(extra.get("published", "")),
        "description": description[:2500],
        "apply_url": url,
        "source": source,
        "source_url": clean(extra.get("source_url", "")),
        "relevance_score": score,
        "status": "REVIEW",
        "verification_note": (
            "Potential role only; Bangladesh eligibility, live vacancy "
            "and payment terms require checking. Missing details are unverified."
        ),
        "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds")
    }

def fetch_source(name, url, parser):
    jobs = []
    try:
        data = get_json(url)
        jobs = parser(data)
        print(f"[OK] {name}: {len(jobs)} relevant listings")
    except Exception as e:
        print(f"[WARN] {name}: {type(e).__name__}: {e}")
    return jobs

def remotive_parser(data):
    result = []
    for j in data.get("jobs", []):
        row = make_job(
            first(j, "title"), first(j, "company_name", "company"),
            first(j, "description", "candidate_required_location"),
            first(j, "url"), "Remotive",
            location=first(j, "candidate_required_location"),
            remote="Remote",
            employment_type=first(j, "job_type"),
            published=first(j, "publication_date"),
            source_url="https://remotive.com"
        )
        if row:
            result.append(row)
    return result

def remoteok_parser(data):
    result = []
    if not isinstance(data, list):
        return result
    for j in data:
        if not isinstance(j, dict) or not j.get("position"):
            continue
        salary = first(j, "salary")
        row = make_job(
            first(j, "position"), first(j, "company"),
            first(j, "description", "tags"), first(j, "url"),
            "Remote OK",
            location=first(j, "location"),
            remote="Remote",
            pay_min=salary,
            source_url="https://remoteok.com"
        )
        if row:
            result.append(row)
    return result

def jobicy_parser(data):
    result = []
    for j in data.get("jobs", []):
        row = make_job(
            first(j, "jobTitle", "title"), first(j, "companyName", "company"),
            first(j, "jobDescription", "description"),
            first(j, "url", "jobUrl"), "Jobicy",
            location=first(j, "jobGeo", "location"),
            remote="Remote",
            eligible_countries=first(j, "jobGeo"),
            employment_type=first(j, "jobType"),
            published=first(j, "pubDate", "published"),
            pay_min=first(j, "annualSalaryMin", "salaryMin"),
            pay_max=first(j, "annualSalaryMax", "salaryMax"),
            currency=first(j, "salaryCurrency"),
            salary_period="year" if first(j, "annualSalaryMin", "annualSalaryMax") else "",
            source_url="https://jobicy.com/jobs-rss-feed"
        )
        if row:
            result.append(row)
    return result

def arbeitnow_parser(data):
    result = []
    for j in data.get("data", []):
        row = make_job(
            first(j, "title"), first(j, "company_name", "company"),
            first(j, "description"), first(j, "url"),
            "Arbeitnow",
            location=first(j, "location"),
            remote="Remote" if j.get("remote") else "",
            employment_type=first(j, "job_types", "employment_type"),
            published=first(j, "created_at"),
            source_url="https://www.arbeitnow.com"
        )
        if row:
            result.append(row)
    return result

def himalayas_parser(data):
    result = []
    items = data.get("jobs", data.get("data", []))
    if isinstance(items, dict):
        items = items.get("jobs", [])
    for j in items:
        row = make_job(
            first(j, "title"), first(j, "companyName", "company"),
            first(j, "description", "excerpt"),
            first(j, "applicationLink", "url", "applicationUrl"),
            "Himalayas",
            location=first(j, "locationRestrictions", "location"),
            eligible_countries=first(j, "locationRestrictions"),
            remote="Remote",
            employment_type=first(j, "employmentType", "employment_type"),
            published=first(j, "pubDate", "publishedAt"),
            source_url="https://himalayas.app/jobs"
        )
        if row:
            result.append(row)
    return result

def main():
    all_jobs = []

    all_jobs += fetch_source(
        "Remotive",
        "https://remotive.com/api/remote-jobs",
        remotive_parser
    )
    time.sleep(1)

    all_jobs += fetch_source(
        "Remote OK",
        "https://remoteok.com/api",
        remoteok_parser
    )
    time.sleep(1)

    all_jobs += fetch_source(
        "Jobicy",
        "https://jobicy.com/api/v2/remote-jobs?count=200&geo=anywhere",
        jobicy_parser
    )
    time.sleep(1)

    all_jobs += fetch_source(
        "Arbeitnow",
        "https://www.arbeitnow.com/api/job-board-api",
        arbeitnow_parser
    )
    time.sleep(1)

    all_jobs += fetch_source(
        "Himalayas",
        "https://himalayas.app/jobs/api/search?" + urlencode({
            "limit": 100,
            "offset": 0,
            "worldwide": "true"
        }),
        himalayas_parser
    )

    # Merge with existing results so earlier leads are not discarded.
    existing = []
    if DEST.exists():
        try:
            with DEST.open(encoding="utf-8-sig", newline="") as f:
                existing = list(csv.DictReader(f))
        except Exception:
            existing = []

    by_url = {}
    for job in existing + all_jobs:
        url = clean(job.get("apply_url", "")).split("?")[0].rstrip("/")
        if not url:
            continue
        if url not in by_url or int(job.get("relevance_score") or 0) > int(
            by_url[url].get("relevance_score") or 0
        ):
            by_url[url] = {field: job.get(field, "") for field in FIELDS}

    jobs = sorted(
        by_url.values(),
        key=lambda j: int(j.get("relevance_score") or 0),
        reverse=True
    )

    with DEST.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(jobs)

    print("\n========== GINNE AI MULTI-SOURCE REPORT ==========")
    print(f"Relevant unique leads saved: {len(jobs)}")
    print(f"Output: {DEST}")
    print("Status: REVIEW means not yet verified.")
    print("No job is marked as confirmed eligible or guaranteed paid.")

    print("\nTop 15 leads:")
    for j in jobs[:15]:
        print(f"- [{j['relevance_score']}] {j['title']} — {j['company']}")
        print(f"  Source: {j['source']} | Pay: {j['pay_min']} "
              f"{j['currency']} {j['salary_period']}")
        print(f"  Apply: {j['apply_url']}")

if __name__ == "__main__":
    main()
