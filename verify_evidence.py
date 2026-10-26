import csv
import re
import time
import html
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

BASE = Path.home() / "GinneAI"
SRC = BASE / "output" / "verification_results.csv"
DEST = BASE / "output" / "job_evidence.csv"

if not SRC.exists():
    print("ERROR: verification_results.csv not found.")
    raise SystemExit(1)

PATTERNS = {
    "bangladesh": r"bangladesh|all countries|eligible countries|country restrictions",
    "worldwide": r"worldwide|work from anywhere|anywhere in the world|global remote",
    "hourly_pay": r"\$\s?\d[\d,.]*(?:\s*[-–]\s*\$?\s?\d[\d,.]*)?\s*(?:/|per\s+)?(?:hour|hr)\b|per hour|hourly rate",
    "salary": r"salary|compensation|pay range|\$\s?\d[\d,.]*\s*(?:k\b|per year|annually|/year)",
    "closed": r"no longer accepting applications|job is closed|position has been filled|job has expired|no longer available",
    "application": r"apply now|apply for this job|submit application|application form",
    "experience": r"no experience|entry.level|junior|years of experience|experience required",
}

def get_page(url):
    req = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (X11; Linux Android 13) AppleWebKit/537.36 Chrome/131 Safari/537.36"
    })
    with urlopen(req, timeout=18) as r:
        return r.status, r.geturl(), r.read(700000).decode("utf-8", "ignore")

def clean_text(raw):
    raw = re.sub(r"(?is)<(script|style|noscript|svg)\b.*?</\1>", " ", raw)
    raw = re.sub(r"(?i)<br\s*/?>|</(p|div|li|h[1-6]|section|article)>", "\n", raw)
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = html.unescape(raw)
    return re.sub(r"[ \t\r]+", " ", raw)

def evidence(text, pattern, limit=3):
    matches = []
    for m in re.finditer(pattern, text, re.I):
        snippet = text[max(0, m.start()-110):min(len(text), m.end()+180)]
        snippet = re.sub(r"\s+", " ", snippet).strip()
        if snippet and snippet not in matches:
            matches.append(snippet)
        if len(matches) >= limit:
            break
    return " || ".join(matches)

with SRC.open(encoding="utf-8-sig", newline="") as f:
    jobs = list(csv.DictReader(f))

out = []
for i, job in enumerate(jobs, 1):
    url = job.get("final_url") or job.get("apply_url", "")
    row = {
        "title": job.get("title", ""),
        "company": job.get("company", ""),
        "url": url,
        "fetch_status": "NOT_CHECKED",
    }

    try:
        status, final_url, raw = get_page(url)
        text = clean_text(raw)
        row["fetch_status"] = f"HTTP_{status}"
        row["final_url"] = final_url
        title = re.search(r"<title[^>]*>(.*?)</title>", raw, re.I | re.S)
        row["page_title"] = clean_text(title.group(1))[:250] if title else ""

        for key, pattern in PATTERNS.items():
            row[key + "_evidence"] = evidence(text, pattern)

        closed = row.get("closed_evidence", "")
        row["review_hint"] = (
            "POSSIBLY_CLOSED" if closed else
            "REVIEW_COUNTRY_AND_PAY" if (
                row.get("bangladesh_evidence") or row.get("worldwide_evidence")
            ) else "MANUAL_REVIEW"
        )
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as e:
        row["fetch_status"] = "FETCH_FAILED"
        row["error"] = str(e)[:200]
        row["review_hint"] = "MANUAL_REVIEW"

    out.append(row)
    print(f"[{i}/{len(jobs)}] {row['title']} — {row['fetch_status']}")
    time.sleep(1)

fields = list(dict.fromkeys(k for r in out for k in r))
with DEST.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
    w.writeheader()
    w.writerows(out)

print("\nEvidence extraction complete.")
print("Saved:", DEST)
print("IMPORTANT: Text clues are not proof of eligibility, pay, or an open vacancy.")
