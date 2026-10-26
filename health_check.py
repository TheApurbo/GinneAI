import csv
import py_compile
from pathlib import Path

ROOT = Path.home() / "GinneAI"
OUT = ROOT / "output"

print("=" * 48)
print("       GINNE AI — SYSTEM HEALTH CHECK")
print("=" * 48)

# 1. Python syntax checks
scripts = sorted(ROOT.glob("*.py"))
failed = []

for script in scripts:
    try:
        py_compile.compile(str(script), doraise=True)
    except Exception as exc:
        failed.append((script.name, str(exc)))

print(f"\n[1] Python files: {len(scripts)}")
print(f"Syntax errors: {len(failed)}")
for name, error in failed:
    print("ERROR:", name, error)

# 2. Output inventory and CSV schemas
print("\n[2] Output files")
csv_files = sorted(OUT.glob("*.csv"))

for path in csv_files:
    try:
        with path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            print(f"\n{path.name}: {len(rows)} rows")
            print("Columns:", ", ".join(reader.fieldnames or []))
    except Exception as exc:
        print(f"\nERROR reading {path.name}: {exc}")

# 3. Duplicate check on the collected leads
source = OUT / "multi_source_jobs.csv"

print("\n[3] Duplicate check")
if source.exists():
    with source.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    url_keys = [
        (r.get("apply_url") or "").strip().lower()
        for r in rows
    ]
    url_keys = [u for u in url_keys if u]

    print("Collected leads:", len(rows))
    print("Unique application URLs:", len(set(url_keys)))
    print("Duplicate application URLs:", len(url_keys) - len(set(url_keys)))
else:
    print("Missing:", source)

# 4. Required folders
print("\n[4] Required folders")
for name in ["input", "output", "review"]:
    path = ROOT / name
    print(f"{name}: {'OK' if path.is_dir() else 'MISSING'}")

print("\nHealth check complete. No files were modified.")
