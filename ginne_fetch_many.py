import json
import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

OUT = Path(__file__).resolve().parent / "output"
SEARCH_FILE = OUT / "search_results.json"
REPORT_FILE = OUT / "multi_source_content_report.md"
DATA_FILE = OUT / "fetched_sources.json"


class PageText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.title_parts = []
        self.in_title = False
        self.skip_depth = 0
        self.tag_stack = []

        self.skip_tags = {
            "script", "style", "noscript", "nav",
            "header", "footer"
        }
        self.skip_words = {
            "navigation", "sidebar", "sphinxsidebar",
            "breadcrumb", "breadcrumbs", "related",
            "theme-switcher", "theme_switcher",
            "mobile-nav", "mobile-navigation",
            "pagefooter", "page-header", "pageheader",
            "toctree-wrapper"
        }

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attrs = dict(attrs)
        classes = attrs.get("class", "").lower()
        element_id = attrs.get("id", "").lower()
        labels = set(classes.split())
        labels.add(element_id)

        should_skip = (
            tag in self.skip_tags
            or any(
                word in label
                for label in labels
                for word in self.skip_words
            )
        )

        self.tag_stack.append((tag, should_skip))
        if should_skip:
            self.skip_depth += 1
        if tag == "title":
            self.in_title = True

    def handle_endtag(self, tag):
        tag = tag.lower()

        if tag == "title":
            self.in_title = False

        for i in range(len(self.tag_stack) - 1, -1, -1):
            if self.tag_stack[i][0] == tag:
                removed = self.tag_stack[i:]
                self.tag_stack = self.tag_stack[:i]
                self.skip_depth -= sum(
                    1 for _, skipped in removed if skipped
                )
                self.skip_depth = max(0, self.skip_depth)
                break

    def handle_data(self, data):
        text = " ".join(data.split())
        if not text:
            return

        if self.in_title:
            self.title_parts.append(text)
        elif not self.skip_depth:
            noise = (
                "theme auto", "table of contents",
                "previous topic", "next topic",
                "navigation index", "report a bug",
                "improve this page", "show source",
            )
            if text.lower() not in noise:
                self.parts.append(text)

def fetch_page(url):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Only HTTPS URLs are allowed.")

    # Avoid fetching local or private network hosts.
    host = parsed.hostname.lower()
    if host == "localhost" or host.endswith(".local"):
        raise ValueError("Local hosts are not allowed.")
    if re.match(r"^(127\.|10\.|192\.168\.|169\.254\.)", host):
        raise ValueError("Private or local network hosts are not allowed.")

    request = urllib.request.Request(
        url, headers={"User-Agent": "GinneAI/1.0 research assistant"}
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        final_url = response.geturl()
        final = urllib.parse.urlparse(final_url)
        if final.scheme != "https":
            raise ValueError("Non-HTTPS redirect blocked.")
        html = response.read(300000).decode("utf-8", "replace")

    parser = PageText()
    parser.feed(html)

    return {
        "url": final_url,
        "title": " ".join(parser.title_parts) or "Untitled page",
        "text_preview": " ".join(parser.parts)[:5000],
        "note": "Preview only; verify claims against the original page."
    }


def main():
    if not SEARCH_FILE.exists():
        print("Search results missing. Run a search first.")
        return

    data = json.loads(SEARCH_FILE.read_text(encoding="utf-8"))
    results = data.get("results", []) if isinstance(data, dict) else []
    pages = []
    seen = set()

    query = str(data.get("query", "")).lower()
    terms = [
        word for word in query.replace("-", " ").split()
        if len(word) > 2
    ]

    candidates = [
        item for item in results
        if isinstance(item, dict) and item.get("url", "").startswith("https://")
    ]

    def relevance(item):
        title = str(item.get("title", "")).lower()
        url = str(item.get("url", "")).lower()
        snippet = str(item.get("snippet", "")).lower()
        score = sum(3 for term in terms if term in title)
        score += sum(2 for term in terms if term in url)
        score += sum(1 for term in terms if term in snippet)

        path = url.split("://", 1)[-1].split("/", 1)
        if len(path) == 1 or path[0].endswith("/"):
            score -= 4
        if len(url.rstrip("/").split("/")) <= 3:
            score -= 1
        return score

    candidates.sort(key=relevance, reverse=True)

    for item in candidates[:5]:
        url = item.get("url", "")
        if url in seen:
            continue
        seen.add(url)

        print(f"Fetching: {url}")
        try:
            page = fetch_page(url)
            pages.append(page)
            print(f"  OK: {page['title']}")
        except Exception as error:
            print(f"  Failed: {error}")
            pages.append({
                "url": url,
                "title": item.get("title", "Unavailable source"),
                "text_preview": "",
                "error": str(error)
            })

    OUT.mkdir(exist_ok=True)
    DATA_FILE.write_text(
        json.dumps(pages, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    lines = [
        "# GinneAI Multi-Source Content Report",
        "",
        f"Query: {data.get('query', 'Unknown')}",
        f"Sources attempted: {len(pages)}",
        "",
    ]

    for i, page in enumerate(pages, 1):
        lines.extend([
            f"## {i}. {page['title']}",
            "",
            f"URL: {page['url']}",
            "",
        ])
        if page.get("text_preview"):
            lines.extend([page["text_preview"], ""])
        else:
            lines.extend([
                f"Content unavailable: {page.get('error', 'Unknown error')}",
                "",
            ])

    lines.extend([
        "## Limitations",
        "",
        "- At most five search results are fetched per run.",
        "- Each page is limited to a 5,000-character text preview.",
        "- Source content is not independently fact-checked.",
        "",
    ])

    REPORT_FILE.write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved source data: {DATA_FILE}")
    print(f"Saved report: {REPORT_FILE}")


if __name__ == "__main__":
    main()
