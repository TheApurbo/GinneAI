import csv
from pathlib import Path

BASE = Path.home() / "GinneAI"
SRC = BASE / "output" / "final_review_queue.csv"
DEST = BASE / "output" / "ranked_job_matches.csv"

if not SRC.exists():
    raise SystemExit("Missing output/final_review_queue.csv")

def score_job(j):
    title = j.get("title", "").lower()
    company = j.get("company", "").lower()
    country = j.get("country_status", "").lower()
    pay = j.get("pay_status", "").lower()
    priority = j.get("priority", "")

    score = 0
    reasons = []

    # Role relevance
    if any(x in title for x in [
        "ai trainer", "video annotation", "data annotator",
        "ai evaluator", "llm evaluator"
    ]):
        score += 30
        reasons.append("AI task relevance")
    elif any(x in title for x in [
        "technical customer support", "technical support",
        "it support", "linux support", "cloud support"
    ]):
        score += 25
        reasons.append("Technical support relevance")
    elif any(x in title for x in [
        "customer support", "customer service"
    ]):
        score += 18
        reasons.append("Customer support relevance")
    elif any(x in title for x in [
        "qa tester", "junior qa", "software tester"
    ]):
        score += 15
        reasons.append("QA relevance")

    # Location clue only; not confirmed eligibility.
    if "bangladesh text found" in country:
        score += 10
        reasons.append("Bangladesh mentioned; context still required")
    elif "worldwide text found" in country:
        score += 7
        reasons.append("Worldwide mentioned; restrictions still required")

    # Pay is unknown unless explicitly verified by a person or reliable job-specific source.
    if "hourly keyword found" in pay:
        score += 2
        reasons.append("Hourly keyword found; rate unconfirmed")

    if priority == "P1 - VERIFY":
        score += 5
    elif priority == "P2 - VERIFY":
        score += 3

    # Exclude known unsuitable categories from high ranking.
    if any(x in title for x in [
        "tier iii", "manager", "director", "principal", "senior engineer"
    ]):
        score -= 20
        reasons.append("Possible experience-level mismatch")

    return score, "; ".join(reasons)

with SRC.open(encoding="utf-8-sig", newline="") as f:
    jobs = list(csv.DictReader(f))

results = []
for j in jobs:
    score, reason = score_job(j)
    row = dict(j)
    row["match_score"] = score
    row["match_reasons"] = reason
    row["bangladesh_eligibility_verified"] = "NO"
    row["hourly_rate_10_usd_or_more_verified"] = "NO"
    row["vacancy_open_verified"] = "NO"
    row["final_decision"] = "NEEDS_VERIFICATION"
    results.append(row)

results.sort(key=lambda r: int(r["match_score"]), reverse=True)

fields = list(dict.fromkeys(k for r in results for k in r))
with DEST.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
    w.writeheader()
    w.writerows(results)

print("Ranked leads:", len(results))
print("Saved:", DEST)
print("\nTOP MATCHES — NOT VERIFIED JOB OFFERS")
for i, j in enumerate(results[:10], 1):
    print(f"\n{i}. Score {j['match_score']} — {j.get('title')} | {j.get('company')}")
    print("Reasons:", j["match_reasons"])
    print("Country:", j["country_status"])
    print("Pay:", j["pay_status"])
    print("Decision:", j["final_decision"])
    print("Apply:", j.get("application_url"))

print("\nNo job is marked as a verified match automatically.")
