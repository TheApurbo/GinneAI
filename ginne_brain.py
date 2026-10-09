import json
import sys
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

OUT = Path(__file__).resolve().parent / "output"
OUT.mkdir(exist_ok=True)

class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.in_title = False
        self.title_parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.skip += 1
        if tag == "title":
            self.in_title = True

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self.skip:
            self.skip -= 1
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        text = " ".join(data.split())
        if not text:
            return
        if self.in_title:
            self.title_parts.append(text)
        if not self.skip:
            self.parts.append(text)

class HTMLParserSnippet:
    @staticmethod
    def clean(value):
        import re
        from html import unescape
        return unescape(re.sub(r"<[^>]+>", "", value))

def search(query):
    q = query.lower()
    results = []

    official_sources = [
        ("python csv", "Python CSV module",
         "https://docs.python.org/3/library/csv.html",
         "Official Python documentation for reading and writing CSV files."),
        ("python", "Python Official Documentation",
         "https://docs.python.org/3/",
         "Official Python language and library documentation."),
        ("linux kernel", "Linux Kernel Documentation",
         "https://docs.kernel.org/",
         "Official Linux kernel documentation."),
        ("ubuntu", "Ubuntu Server Documentation",
         "https://ubuntu.com/server/docs",
         "Official Ubuntu Server documentation."),
        ("debian", "Debian Documentation",
         "https://www.debian.org/doc/",
         "Official Debian documentation."),
        ("kubernetes", "Kubernetes Documentation",
         "https://kubernetes.io/docs/",
         "Official Kubernetes documentation."),
        ("docker", "Docker Documentation",
         "https://docs.docker.com/",
         "Official Docker documentation."),
        ("git", "Git Documentation",
         "https://git-scm.com/doc",
         "Official Git documentation.")
    ]

    # Return multiple relevant official sources when available.
    if "csv" in q and "python" in q:
        matches = [
            official_sources[0],
            official_sources[1],
        ]
    elif "linux kernel" in q:
        matches = [official_sources[2]]
    elif "ubuntu" in q:
        matches = [official_sources[3]]
    elif "debian" in q:
        matches = [official_sources[4]]
    elif "kubernetes" in q:
        matches = [official_sources[5]]
    elif "docker" in q:
        matches = [official_sources[6]]
    elif "git" in q:
        matches = [official_sources[7]]
    elif "python" in q:
        matches = [official_sources[1]]
    else:
        matches = []

    for _, title, url, snippet in matches:
        results.append({
            "title": title,
            "url": url,
            "snippet": snippet,
            "source": "Official documentation"
        })

    # Use Wikipedia only when no official route matches.
    if not results:
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": 10,
            "format": "json"
        }
        url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(
            url, headers={"User-Agent": "GinneAI/1.0 (research assistant)"}
        )

        with urllib.request.urlopen(req, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))

        for item in data.get("query", {}).get("search", []):
            title = item.get("title", "")
            results.append({
                "title": title,
                "url": "https://en.wikipedia.org/wiki/" +
                       urllib.parse.quote(title.replace(" ", "_")),
                "snippet": HTMLParserSnippet.clean(item.get("snippet", "")),
                "source": "Wikipedia API"
            })

    (OUT / "search_results.json").write_text(
        json.dumps({"query": query, "results": results}, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    source_names = sorted(set(item["source"] for item in results))
    report = [
        "# Ginne AI Research Report", "",
        "Query: " + query, "",
        "Sources: " + (", ".join(source_names) if source_names else "No results"),
        ""
    ]

    for i, item in enumerate(results, 1):
        report.extend([
            f"## {i}. {item['title']}",
            "Source: " + item["source"],
            item["url"],
            item["snippet"], ""
        ])

    (OUT / "research_report.md").write_text(
        "\n".join(report), encoding="utf-8"
    )

    print(f"Search complete: {len(results)} results found.")
    print("Saved: output/search_results.json")
    print("Saved: output/research_report.md")
    for item in results[:5]:
        print("-", item["title"], "|", item["url"])

def fetch(url):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Please provide a valid HTTPS URL.")

    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        final_url = response.geturl()
        if urllib.parse.urlparse(final_url).scheme != "https":
            raise ValueError("Non-HTTPS redirect blocked.")
        html = response.read(300000).decode("utf-8", "replace")

    parser = TextExtractor()
    parser.feed(html)
    result = {
        "url": final_url,
        "title": " ".join(parser.title_parts),
        "text_preview": " ".join(parser.parts)[:5000],
        "note": "Verify facts against the original source."
    }
    (OUT / "fetched_page.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))

def add_task(description):
    path = OUT / "task_queue.json"
    if path.exists():
        try:
            tasks = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            tasks = []
    else:
        tasks = []

    if not isinstance(tasks, list):
        tasks = []

    task = {
        "id": len(tasks) + 1,
        "description": description,
        "status": "needs_human_review"
        if any(word in description.lower() for word in (
            "payment", "password", "delete", "purchase",
            "submit application", "private data"
        )) else "queued"
    }
    tasks.append(task)
    path.write_text(
        json.dumps(tasks, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    print(json.dumps(task, indent=2, ensure_ascii=False))

def main():
    if len(sys.argv) < 2:
        print('Commands:')
        print('  python ginne_brain.py search "your research topic"')
        print('  python ginne_brain.py fetch "https://example.com"')
        print('  python ginne_brain.py add "task description"')
        print('  python ginne_brain.py queue')
        return

    action = sys.argv[1].lower()

    try:
        if action == "search" and len(sys.argv) >= 3:
            search(" ".join(sys.argv[2:]))
        elif action == "fetch" and len(sys.argv) == 3:
            fetch(sys.argv[2])
        elif action == "add" and len(sys.argv) >= 3:
            add_task(" ".join(sys.argv[2:]))
        elif action == "queue":
            path = OUT / "task_queue.json"
            print(path.read_text(encoding="utf-8")
                  if path.exists() else "Task queue is empty.")
        else:
            print("Unknown command. Run: python ginne_brain.py")
    except Exception as error:
        print(f"Task failed: {type(error).__name__}: {error}")

if __name__ == "__main__":
    main()
