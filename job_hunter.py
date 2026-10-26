import csv
import html
import json
import re
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
PROFILE_FILE = ROOT / "config/job_profile.json"
INPUT_FILE = ROOT / "input/jobs.csv"
CACHE_FILE = ROOT / "output/remotive_cache.json"
OUTPUT_FILE = ROOT / "output/job_matches.csv"
RAW_FILE = ROOT / "output/discovered_jobs.csv"

API = "https://remotive.com/api/remote-jobs?limit=200"
CACHE_SECONDS = 6 * 60 * 60

FIELDS = [
    "title", "company", "location", "remote",
    "eligible_countries", "pay_type", "pay_min_usd",
    "description", "apply_url", "source"
]


def load_profile():
    return json.loads(PROFILE_FILE.read_text(encoding="utf-8"))


def clean_text(value):
    value = re.sub(r"<[^>]*>", " ", str(value or ""))
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def fetch_jobs():
    # Cache successful responses to respect the source's refresh limits.
    if CACHE_FILE.exists():
        try:
            cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            age = time.time() - cache["fetched_at"]
            if age < CACHE_SECONDS and isinstance(cache.get("jobs"), list):
                print(f"Using cached data ({int(age / 60)} minutes old).")
                return cache["jobs"]
        except (ValueError, KeyError, OSError):
            pass

    request = Request(API, headers={
        "User-Agent": "GinneAI-JobHunter/1.0 (personal job search)",
        "Accept": "application/json"
    })

    try:
        with urlopen(request, timeout=25) as response:
            data = json.loads(response.read().decode("utf-8"))
        jobs = data.get("jobs", [])
        if not isinstance(jobs, list):
            raise ValueError("Unexpected API response format")

        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps({
            "fetched_at": time.time(),
            "jobs": jobs
        }, ensure_ascii=False), encoding="utf-8")
        return jobs

    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        print("Live fetch failed:", str(exc)[:200])
        if CACHE_FILE.exists():
            print("Trying previously cached results.")
            try:
                return json.loads(
                    CACHE_FILE.read_text(encoding="utf-8")
                ).get("jobs", [])
            except (ValueError, OSError):
                pass
        return []


def normalize(job):
    location = clean_text(job.get("candidate_required_location"))
    salary = clean_text(job.get("salary"))
    salary_lower = salary.lower()

    # Only mark hourly when the listing explicitly indicates hourly pay.
    if re.search(r"\b(per hour|hourly|/hour|/hr|per hr)\b", salary_lower):
        pay_type = "hourly"
        numbers = re.findall(r"\d[\d,]*(?:\.\d+)?", salary)
        pay_min = numbers[0].replace(",", "") if numbers else ""
    elif re.search(r"\b(per year|yearly|annual|annually|per month|monthly)\b",
                   salary_lower):
        pay_type = "non_hourly"
        pay_min = ""
    else:
        pay_type = "unknown"
        pay_min = ""

    # The API returns remote jobs, but candidate country restrictions vary.
    loc_lower = location.lower()
    if any(term in loc_lower for term in (
        "worldwide", "anywhere in the world", "all countries"
    )):
        eligible = "Worldwide"
    elif "bangladesh" in loc_lower:
        eligible = "Bangladesh"
    elif not location or loc_lower in {"anywhere", "not specified"}:
        eligible = "unknown"
    else:
        eligible = location

    return {
        "title": clean_text(job.get("title")),
        "company": clean_text(job.get("company_name")),
        "location": location or "Not specified",
        "remote": "yes",
        "eligible_countries": eligible,
        "pay_type": pay_type,
        "pay_min_usd": pay_min,
        "description": clean_text(job.get("description")),
        "apply_url": str(job.get("url", "")).strip(),
        "source": "Remotive"
    }


def evaluate(job, profile):
    url = job["apply_url"]
    parsed = urlparse(url)

    if parsed.scheme != "https" or not parsed.hostname:
        return "REJECT", 0, "Invalid application URL"

    if parsed.hostname.lower() not in {"remotive.com", "www.remotive.com"}:
        return "REVIEW", 0, "Check application link and source"

    if not job["title"] or not job["company"]:
        return "REVIEW", 0, "Missing title or company"

    location = job["eligible_countries"].lower()
    if location == "unknown":
        return "REVIEW", 0, "Candidate country eligibility unknown"

    if "bangladesh" not in location and "worldwide" not in location:
        return "REVIEW", 0, "Confirm whether Bangladesh is eligible"

    if job["pay_type"] == "non_hourly":
        return "REJECT", 0, "Listing indicates non-hourly pay"

    if job["pay_type"] != "hourly":
        return "REVIEW", 0, "Hourly pay not confirmed"

    try:
        pay = float(job["pay_min_usd"])
    except (ValueError, TypeError):
        return "REVIEW", 0, "Hourly pay amount not confirmed"

    if pay < float(profile.get("minimum_hourly_usd", 10)):
        return "REJECT", 0, "Below minimum hourly pay"

    text = (job["title"] + " " + job["description"]).lower()
    matched = [
        word for word in profile.get("keywords", [])
        if word.lower() in text
    ]
    if not matched:
        return "REVIEW", 0, "No configured job keywords matched"

    score = min(100, round(50 + 50 * len(matched) /
                            max(1, len(profile["keywords"]))))
    return "MATCH", score, "Check original listing before applying"


def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def discover():
    profile = load_profile()
    jobs = fetch_jobs()
    if not jobs:
        print("No live or cached jobs available.")
        return

    normalized = []
    seen = set()

    for item in jobs:
        job = normalize(item)
        if job["apply_url"] in seen or not job["apply_url"]:
            continue
        seen.add(job["apply_url"])
        normalized.append(job)

    write_csv(RAW_FILE, normalized, FIELDS)

    results = []
    for job in normalized:
        status, score, reason = evaluate(job, profile)
        results.append({
            **job,
            "status": status,
            "score": score,
            "reason": reason
        })

    result_fields = FIELDS + ["status", "score", "reason"]
    write_csv(OUTPUT_FILE, results, result_fields)

    counts = {}
    for item in results:
        counts[item["status"]] = counts.get(item["status"], 0) + 1

    print(f"Unique jobs discovered: {len(normalized)}")
    print(f"Results: {RAW_FILE.relative_to(ROOT)}")
    print(f"Eligibility report: {OUTPUT_FILE.relative_to(ROOT)}")
    print("Statuses:", json.dumps(counts))
    print("\nFirst 10 listings:")
    for item in results[:10]:
        print(f"[{item['status']}] {item['title']} — {item['company']}")
        print("  Location:", item["location"])
        print("  Pay:", item["pay_type"], item["pay_min_usd"])
        print("  Source: Remotive")
        print("  Apply:", item["apply_url"])


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in {"fetch", "profile"}:
        print("Usage: python job_hunter.py [fetch|profile]")
        raise SystemExit(2)

    if sys.argv[1] == "profile":
        print(json.dumps(load_profile(), indent=2))
    else:
        discover()


if __name__ == "__main__":
    main()
