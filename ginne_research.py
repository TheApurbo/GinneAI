import json
from pathlib import Path
from urllib.parse import urlparse

OUTPUT = Path(__file__).resolve().parent / "output"
SEARCH_FILE = OUTPUT / "search_results.json"
REPORT_FILE = OUTPUT / "multi_source_report.md"


def valid_http_url(url):
    try:
        parsed = urlparse(url)
        return parsed.scheme == "https" and bool(parsed.netloc)
    except (TypeError, ValueError):
        return False


def main():
    if not SEARCH_FILE.exists():
        print("Search results not found. Run a search first.")
        return

    try:
        data = json.loads(SEARCH_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as error:
        print(f"Could not read search results: {error}")
        return

    # Accept either a list or a dictionary containing a results list.
    if isinstance(data, dict):
        results = data.get("results", [])
        if not results:
            results = data.get("items", [])
    elif isinstance(data, list):
        results = data
    else:
        results = []

    unique = []
    seen = set()

    for item in results:
        if not isinstance(item, dict):
            continue

        url = item.get("url", "")
        if not valid_http_url(url) or url in seen:
            continue

        seen.add(url)
        unique.append(item)

    lines = [
        "# GinneAI Multi-Source Research",
        "",
        f"Sources collected: {len(unique)}",
        "",
        "> This report organizes search results. It does not independently",
        "> verify claims or combine full page contents.",
        "",
        "## Sources",
        "",
    ]

    if not unique:
        lines.append(
            "No valid HTTPS sources found. Run a search and inspect "
            "output/search_results.json."
        )

    for number, item in enumerate(unique, start=1):
        title = str(item.get("title") or "Untitled source")
        url = item.get("url", "")
        description = str(
            item.get("description")
            or item.get("snippet")
            or item.get("summary")
            or ""
        )

        lines.extend([
            f"### {number}. {title}",
            "",
            f"URL: {url}",
            "",
        ])

        if description:
            lines.extend([description, ""])

    lines.extend([
        "## Verification checklist",
        "",
        "- Open the original source before relying on a claim.",
        "- Compare important facts across independent sources.",
        "- Treat missing descriptions as unknown, not as confirmed facts.",
        "",
    ])

    REPORT_FILE.write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved report: {REPORT_FILE}")
    print(f"Unique HTTPS sources: {len(unique)}")


if __name__ == "__main__":
    main()
