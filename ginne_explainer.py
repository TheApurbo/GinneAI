import json
from pathlib import Path

source = Path("output/fetched_page.json")
target = Path("output/summary_report.md")

if not source.exists():
    print("No fetched page found. Run a fetch command first.")
    raise SystemExit(1)

data = json.loads(source.read_text(encoding="utf-8"))
title = data.get("title", "Untitled page")
url = data.get("url", "")
content = data.get("text_preview", "").lower()

lines = [
    "# GinneAI — Research Notes",
    "",
    f"**Title:** {title}",
    f"**Source:** {url}",
    "",
    "## Beginner-friendly explanation",
    "",
]

if "dictreader" in content and "dictwriter" in content:
    lines.append(
        "- `DictReader` reads CSV rows as dictionaries. "
        "`DictWriter` writes dictionary data into CSV files."
    )

if "csv module implements classes" in content:
    lines.append(
        "- Python's `csv` module helps programs read and write "
        "table-shaped data stored in CSV format."
    )

if "excel" in content:
    lines.append(
        "- The module can handle CSV data used by spreadsheet "
        "programs such as Microsoft Excel."
    )

lines.extend([
    "",
    "## Limitations",
    "",
    "- These explanations use simple rules, not an AI language model.",
    "- Only the saved page preview was checked.",
    "- Verify important details against the original documentation.",
    "",
])

target.write_text("\n".join(lines), encoding="utf-8")
print(f"Report saved to: {target}")
