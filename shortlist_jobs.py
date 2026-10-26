import csv
import re
from pathlib import Path

src = Path("output/multi_source_jobs.csv")
dest = Path("output/priority_leads.csv")

priority_roles = {
    "AI annotation / trainer": [
        "data annotator", "data annotation", "data label",
        "ai trainer", "ai evaluator", "video annotation",
        "image annotation", "llm evaluator", "ai safety evaluator",
        "response evaluator", "bengali ai"
    ],
    "Technical support": [
        "technical support", "technical customer support",
        "it support", "help desk", "service desk",
        "linux support", "cloud support", "support engineer",
        "customer support", "customer service"
    ],
    "Entry-level QA": [
        "qa tester", "junior qa", "entry level qa",
        "software tester", "manual tester"
    ],
    "Engineering tasks": [
        "pcb design", "kicad", "autocad", "cad technician",
        "technical drawing", "electronics technician",
        "electronics engineer", "avionics"
    ]
}

exclude = [
    "manager", "director", "head of ", "vice president",
    "principal engineer", "staff engineer", "senior mechanical",
    "engineering lead", "team lead"
]

def classify(title):
    t = title.lower()
    if any(x in t for x in exclude):
        return ""
    for category, terms in priority_roles.items():
        if any(term in t for term in terms):
            return category
    return ""

with src.open(encoding="utf-8-sig", newline="") as f:
    jobs = list(csv.DictReader(f))

results = []
seen = set()

for j in jobs:
    title = j.get("title", "").strip()
    company = j.get("company", "").strip()
    url = j.get("apply_url", "").strip()

    # Canonical excluded for now, per your current job-search plan.
    if "canonical" in company.lower():
        continue

    category = classify(title)
    if not category or not url.startswith("https://"):
        continue

    key = url.split("?")[0].rstrip("/").lower()
    if not key or key in seen:
        continue
    seen.add(key)

    j["priority_category"] = category
    j["verification_status"] = "NOT VERIFIED"
    j["next_action"] = "Check live vacancy, Bangladesh eligibility and pay"
    results.append(j)

order = {
    "AI annotation / trainer": 0,
    "Technical support": 1,
    "Entry-level QA": 2,
    "Engineering tasks": 3
}
results.sort(key=lambda j: (
    order.get(j["priority_category"], 9),
    j.get("title", "").lower()
))

fields = list(results[0].keys()) if results else [
    "title", "company", "apply_url",
    "priority_category", "verification_status", "next_action"
]

with dest.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(results)

print(f"Priority leads: {len(results)}")
print(f"Saved to: {dest}\n")

for i, j in enumerate(results[:35], 1):
    print(f"{i}. [{j['priority_category']}] {j.get('title','')} — {j.get('company','')}")
    print(f"   Pay: {j.get('pay_min','')}–{j.get('pay_max','')} "
          f"{j.get('currency','')} / {j.get('salary_period','')}")
    print(f"   Country: {j.get('eligible_countries') or j.get('location') or 'Not specified'}")
    print(f"   Apply: {j.get('apply_url','')}\n")

if not results:
    print("No matching titles. We will broaden the title filters.")
