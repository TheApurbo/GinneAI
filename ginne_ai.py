import csv
import re
import sys
import time
from pathlib import Path
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
INBOX = ROOT / "input"
OUT = ROOT / "output"
REVIEW = ROOT / "review"

for folder in (INBOX, OUT, REVIEW):
    folder.mkdir(parents=True, exist_ok=True)


class PageText(HTMLParser):
    """Extract visible-ish text and page title from HTML."""
    def __init__(self):
        super().__init__()
        self.title = ""
        self.in_title = False
        self.skip = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() in ("script", "style", "noscript", "svg"):
            self.skip += 1
        if tag.lower() == "title":
            self.in_title = True

    def handle_endtag(self, tag):
        if tag.lower() in ("script", "style", "noscript", "svg"):
            self.skip = max(0, self.skip - 1)
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data):
        text = " ".join(data.split())
        if not text:
            return
        if self.in_title:
            self.title += " " + text
        if not self.skip:
            self.parts.append(text)


def clean_csv(source, destination):
    """Trim whitespace, remove exact duplicate rows, flag missing fields."""
    source = Path(source)
    destination = Path(destination)

    if not source.exists():
        print("Input CSV not found:", source)
        return

    with source.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            print("ERROR: CSV must have a header row.")
            return
        headers = [h.strip() for h in reader.fieldnames]
        rows = []
        seen = set()
        duplicates = 0
        missing = []

        for line_no, raw in enumerate(reader, start=2):
            row = {}
            for old_key, new_key in zip(reader.fieldnames, headers):
                value = raw.get(old_key, "")
                row[new_key] = (value or "").strip()

            signature = tuple(row.get(h, "") for h in headers)
            if signature in seen:
                duplicates += 1
                continue
            seen.add(signature)
            rows.append(row)

            blanks = [h for h in headers if not row.get(h, "")]
            if blanks:
                missing.append({
                    "source_row": line_no,
                    "missing_fields": ", ".join(blanks),
                    "status": "HUMAN_REVIEW"
                })

    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)

    review_file = REVIEW / "missing_fields.csv"
    with review_file.open("w", newline="", encoding="utf-8") as f:
        fields = ["source_row", "missing_fields", "status"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(missing)

    print("CLEAN COMPLETE")
    print("Rows kept:", len(rows))
    print("Duplicate rows removed:", duplicates)
    print("Rows needing review:", len(missing))
    print("Clean file:", destination)
    print("Review file:", review_file)


def research_urls(url_file):
    """Fetch only explicitly supplied public HTTP(S) URLs.
    No login, forms, CAPTCHA solving, or automated submissions.
    """
    url_file = Path(url_file)
    if not url_file.exists():
        print("Create the URL list first:", url_file)
        return

    urls = [
        line.strip() for line in
        url_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    results = []
    for url in urls:
        parsed = urlparse(url)
        row = {
            "url": url,
            "domain": parsed.netloc,
            "title": "",
            "excerpt": "",
            "status": "HUMAN_REVIEW"
        }

        if parsed.scheme != "https" or not parsed.hostname:
            row["status"] = "SKIPPED_UNSAFE_URL"
            results.append(row)
            continue

        if parsed.username or parsed.password:
            row["status"] = "SKIPPED_URL_CREDENTIALS"
            results.append(row)
            continue

        try:
            request = Request(
                url,
                headers={"User-Agent": "GinneAI/0.1 (manual public research)"}
            )
            with urlopen(request, timeout=12) as response:
                content_type = response.headers.get("Content-Type", "")
                if "text/html" not in content_type.lower():
                    row["status"] = "SKIPPED_NOT_HTML"
                    results.append(row)
                    continue
                html = response.read(500_000).decode("utf-8", errors="replace")

            parser = PageText()
            parser.feed(html)
            row["title"] = re.sub(r"\s+", " ", parser.title).strip()
            row["excerpt"] = re.sub(
                r"\s+", " ", " ".join(parser.parts)
            ).strip()[:700]
            row["status"] = "REVIEW_REQUIRED"
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            row["status"] = "FETCH_FAILED: " + str(exc)[:160]

        results.append(row)
        time.sleep(2)

    target = OUT / "research_results.csv"
    with target.open("w", newline="", encoding="utf-8") as f:
        fields = ["url", "domain", "title", "excerpt", "status"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)

    print("Research complete. Human verification is still required.")
    print("Pages processed:", len(results))
    print("Results:", target)


def dashboard():
    print("\n=== GINNE AI STATUS ===")
    for folder in (INBOX, OUT, REVIEW):
        print("\n" + folder.name + ":")
        files = sorted(folder.glob("*"))
        if not files:
            print("  (empty)")
        for file in files:
            if file.is_file():
                print(" ", file.name, "-", file.stat().st_size, "bytes")
    print("\nNo income is assumed or guaranteed.")


def main():
    if len(sys.argv) < 2:
        print("Commands:")
        print(" python taskpilot.py demo")
        print(" python taskpilot.py clean input/sample.csv")
        print(" python taskpilot.py research input/urls.txt")
        print(" python taskpilot.py status")
        return

    command = sys.argv[1].lower()
    if command == "demo":
        sample = INBOX / "sample.csv"
        if not sample.exists():
            with sample.open("w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["name", "email", "company"])
                w.writerow(["  Rina ", "rina@example.com", "North Ltd"])
                w.writerow(["Rina", "rina@example.com", "North Ltd"])
                w.writerow(["Sam", "", "South Ltd"])
                w.writerow([" Lee ", "lee@example.com ", "West Ltd"])
        clean_csv(sample, OUT / "sample_clean.csv")
    elif command == "clean" and len(sys.argv) == 3:
        clean_csv(sys.argv[2], OUT / "cleaned.csv")
    elif command == "research" and len(sys.argv) == 3:
        research_urls(sys.argv[2])
    elif command == "status":
        dashboard()
    else:
        print("Unknown command. Run: python taskpilot.py")


if __name__ == "__main__":
    main()
