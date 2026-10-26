import html as html_module
import csv
import json
import re
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

BASE = Path.home() / "GinneAI"
SRC = BASE / "output" / "priority_leads.csv"
DEST = BASE / "output" / "verification_results.csv"
REPORT = BASE / "output" / "verification_report.md"

if not SRC.exists():
    print("ERROR: output/priority_leads.csv not found.")
    print("Run your shortlist_jobs.py first.")
    raise SystemExit(1)

def fetch(url):
    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; GinneAIJobResearch/1.0)"
        }
    )
    with urlopen(req, timeout=15) as response:
        return response.status, response.geturl(), response.read(400000).decode(
            "utf-8", errors="ignore"
        )

with SRC.open(encoding="utf-8-sig", newline="") as f:
    jobs = list(csv.DictReader(f))

results = []
for i, job in enumerate(jobs, 1):
    url = job.get("apply_url", "").strip()
    title = job.get("title", "").strip()
    company = job.get("company", "").strip()

    row = dict(job)
    row["page_check"] = "NOT_CHECKED"
    row["http_status"] = ""
    row["final_url"] = ""
    row["page_title"] = ""
    row["bangladesh_check"] = "MANUAL_CHECK"
    row["pay_check"] = "MANUAL_CHECK"
    row["live_status"] = "UNCONFIRMED"
    row["verification_notes"] = ""

    if not url.startswith("https://"):
        row["page_check"] = "INVALID_URL"
        row["verification_notes"] = "No valid HTTPS application URL."
        results.append(row)
        continue

    try:
        status, final_url, html = fetch(url)
        row["http_status"] = status
        row["final_url"] = final_url
        row["page_check"] = "PAGE_REACHED" if status == 200 else "HTTP_ERROR"

        match = re.search(
            r"<title[^>]*>(.*?)</title>", html,
            flags=re.IGNORECASE | re.DOTALL
        )
        if match:
            row["page_title"] = re.sub(
                r"\s+", " ", re.sub(r"<[^>]+>", "", match.group(1))
            ).strip()[:250]

        text = re.sub(r"<script\b.*?</script>|<style\b.*?</style>",
                      " ", html, flags=re.I | re.S)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).lower()

        closed_patterns = [
            "job is no longer available",
            "position has been filled",
            "this job is closed",
            "job has expired",
            "no longer accepting applications",
            "this job has expired"
        ]

        if any(p in text for p in closed_patterns):
            row["live_status"] = "POSSIBLY_CLOSED"
            row["verification_notes"] = (
                "Page contains a possible closed-job message; manual confirmation needed."
            )
        else:
            row["live_status"] = "PAGE_REACHABLE_NOT_CONFIRMED"
            row["verification_notes"] = (
                "Page loaded; this does NOT prove the vacancy is open."
            )

        # Only explicit text clues; absence of a clue is not proof.
        if "bangladesh" in text:
            row["bangladesh_check"] = "BANGLADESH_MENTIONED_CHECK_CONTEXT"
        elif "worldwide" in text or "work from anywhere" in text:
            row["bangladesh_check"] = "WORLDWIDE_CLAIM_CHECK_EXCEPTIONS"

        # Detect hourly, monthly and annual pay mentions.
        # Detection is not proof that the employer actually pays this amount.
        pay_patterns = [
            (
                "HOURLY",
                r"(?P<currency>usd|eur|gbp|cad|aud|[$€£])?\s*"
                r"(?P<low>\d[\d,]*(?:\.\d+)?)"
                r"(?:\s*(?:-|–|—|to)\s*(?:usd|eur|gbp|cad|aud|[$€£])?\s*"
                r"(?P<high>\d[\d,]*(?:\.\d+)?))?"
                r"\s*(?:/\s*(?:hour|hr)\b|per\s+hour\b|per\s+hr\b|"
                r"hourly\b|an?\s+hour\b)",
            ),
            (
                "MONTHLY",
                r"(?P<currency>usd|eur|gbp|cad|aud|[$€£])?\s*"
                r"(?P<low>\d[\d,]*(?:\.\d+)?)"
                r"(?:\s*(?:-|–|—|to)\s*(?:usd|eur|gbp|cad|aud|[$€£])?\s*"
                r"(?P<high>\d[\d,]*(?:\.\d+)?))?"
                r"\s*(?:/\s*(?:month|mo)\b|per\s+month\b|"
                r"monthly\b|a\s+month\b)",
            ),
            (
                "ANNUAL",
                r"(?P<currency>usd|eur|gbp|cad|aud|[$€£])?\s*"
                r"(?P<low>\d[\d,]*(?:\.\d+)?)"
                r"(?:\s*(?:-|–|—|to)\s*(?:usd|eur|gbp|cad|aud|[$€£])?\s*"
                r"(?P<high>\d[\d,]*(?:\.\d+)?))?"
                r"\s*(?:/\s*(?:year|yr|annum)\b|per\s+(?:year|annum)\b|"
                r"annually\b|annual\b|yearly\b|a\s+year\b)",
            ),
        ]

        row["pay_type_detected"] = "UNKNOWN"
        row["pay_min_detected"] = ""
        row["pay_max_detected"] = ""
        row["pay_currency_detected"] = ""
        row["monthly_equivalent_min"] = ""
        row["monthly_equivalent_max"] = ""
        row["pay_verification_status"] = "UNVERIFIED"
        row["pay_evidence_note"] = "No supported salary pattern detected."
        row["pay_evidence_context"] = ""

        # Decode HTML entities before matching salary ranges.
        text = html_module.unescape(text)

        for pay_type, pattern in pay_patterns:
            match = re.search(pattern, text, flags=re.I)
            if not match:
                continue

            left = max(0, match.start() - 120)
            right = min(len(text), match.end() + 120)
            row["pay_evidence_context"] = text[left:right]

            def parse_amount(value):
                return float(value.replace(",", "")) if value else None

            low = parse_amount(match.group("low"))
            high = parse_amount(match.group("high"))
            currency = (match.group("currency") or "").upper()

            if currency == "$":
                currency = "USD"
            elif currency == "€":
                currency = "EUR"
            elif currency == "£":
                currency = "GBP"

            row["pay_type_detected"] = pay_type
            row["pay_min_detected"] = low if low is not None else ""
            row["pay_max_detected"] = high if high is not None else ""
            row["pay_currency_detected"] = currency
            row["pay_verification_status"] = (
                "NEEDS_REVIEW" if high is None else "UNVERIFIED"
            )
            row["pay_evidence_note"] = (
                f"{pay_type} salary pattern found in fetched page text; "
                "employer confirmation and context still required."
            )

            if pay_type == "HOURLY":
                row["pay_check"] = "HOURLY_RATE_MENTIONED_CHECK_AMOUNT"
                row["monthly_equivalent_min"] = ""
                row["monthly_equivalent_max"] = ""
            elif pay_type == "MONTHLY":
                row["pay_check"] = "MONTHLY_SALARY_MENTIONED_CHECK_AMOUNT"
                row["monthly_equivalent_min"] = low if low is not None else ""
                row["monthly_equivalent_max"] = high if high is not None else ""
            else:
                row["pay_check"] = "ANNUAL_SALARY_MENTIONED_CHECK_AMOUNT"
                row["monthly_equivalent_min"] = (
                    round(low / 12, 2) if low is not None else ""
                )
                row["monthly_equivalent_max"] = (
                    round(high / 12, 2) if high is not None else ""
                )

            break
        else:
            row["pay_check"] = "NO_SUPPORTED_SALARY_PATTERN_FOUND"


    except HTTPError as e:
        row["page_check"] = "HTTP_ERROR"
        row["http_status"] = e.code
        row["verification_notes"] = (
            "Page returned an HTTP error; this alone does not prove the job is closed."
        )
    except (URLError, TimeoutError, OSError, ValueError) as e:
        row["page_check"] = "FETCH_FAILED"
        row["verification_notes"] = f"Could not fetch page: {str(e)[:180]}"

    results.append(row)
    print(
        f"[{i}/{len(jobs)}] {title} — {company}: "
        f"{row['page_check']} | {row['live_status']}"
    )
    time.sleep(1)

fields = list(dict.fromkeys(k for row in results for k in row.keys()))
with DEST.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(results)

reachable = sum(r["page_check"] == "PAGE_REACHED" for r in results)
failed = len(results) - reachable

with REPORT.open("w", encoding="utf-8") as f:
    f.write("# Ginne AI Job Verification Report\n\n")
    f.write(f"- Leads checked: {len(results)}\n")
    f.write(f"- Pages returned HTTP 200: {reachable}\n")
    f.write(f"- Other fetch results: {failed}\n\n")
    f.write("HTTP 200 means only that a page responded. It does not verify ")
    f.write("job availability, Bangladesh eligibility, or pay.\n\n")
    for r in results:
        f.write(f"## {r.get('title','')} — {r.get('company','')}\n")
        f.write(f"- Page check: {r['page_check']}\n")
        f.write(f"- Live status: {r['live_status']}\n")
        f.write(f"- Bangladesh: {r['bangladesh_check']}\n")
        f.write(f"- Pay: {r['pay_check']}\n")
        f.write(f"- Application: {r.get('apply_url','')}\n\n")

print("\n========== VERIFICATION SUMMARY ==========")
print(f"Leads checked: {len(results)}")
print(f"Pages returned HTTP 200: {reachable}")
print(f"Other results: {failed}")
print(f"CSV: {DEST}")
print(f"Report: {REPORT}")
print("\nNote: No job is automatically marked VERIFIED.")
