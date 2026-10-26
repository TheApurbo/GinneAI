import csv
import sys
from pathlib import Path
from schemas.job_schema import CANONICAL_FIELDS, normalize_job

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"

DEFAULT_INPUT = "multi_source_jobs.csv"
source_name = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_INPUT
source = OUT / source_name
destination = OUT / "canonical_jobs.csv"

if not source.exists():
    print(f"ERROR: Input file not found: {source}")
    print("Available CSV files:")
    for path in sorted(OUT.glob("*.csv")):
        print(" -", path.name)
    raise SystemExit(1)

with source.open("r", encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))

normalized = [normalize_job(row) for row in rows]

# Preserve any existing canonical output before replacing it.
if destination.exists():
    backup = OUT / "canonical_jobs.previous.csv"
    if not backup.exists():
        backup.write_bytes(destination.read_bytes())
        print("Previous canonical output backed up.")

with destination.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=CANONICAL_FIELDS)
    writer.writeheader()
    writer.writerows(normalized)

print("Normalization complete.")
print("Input:", source.name)
print("Input rows:", len(rows))
print("Output:", destination.name)
print("Output rows:", len(normalized))
print("Canonical columns:", len(CANONICAL_FIELDS))
print("Eligibility remains unverified unless explicit evidence exists.")
