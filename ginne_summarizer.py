import json
import re
from pathlib import Path

OUT = Path("output")
SOURCE = OUT / "fetched_page.json"
REPORT = OUT / "summary_report.md"

def summarize(text, max_sentences=8):
    text = re.sub(r"\s+", " ", text).strip()
    sentences = re.split(r"(?<=[.!?])\s+", text)

    # Remove navigation-heavy and duplicate sentences.
    blocked = (
        "table of contents", "previous topic", "next topic",
        "navigation index", "report a bug", "improve this page",
        "theme auto", "show source", "this page"
    )

    cleaned = []
    seen = set()
    for sentence in sentences:
        if sentence.strip().lower().startswith(
            "still, while the delimiters"
        ):
            continue
        sentence = sentence.strip()
        lower = sentence.lower()
        if len(sentence) < 45:
            continue
        if any(word in lower for word in blocked):
            continue
        key = lower
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(sentence)

    sentences = cleaned

    if not sentences:
        return ["No useful sentences found in the fetched content."]

    # Prefer informative sentences with relevant technical terms.
    keywords = (
        "module", "function", "class", "reader", "writer",
        "data", "file", "example", "format", "python"
    )

    ranked = []
    for index, sentence in enumerate(sentences):
        lower = sentence.lower()
        score = sum(lower.count(word) for word in keywords)
        score += min(len(sentence) / 200, 1)
        ranked.append((score, index, sentence))

    chosen = sorted(ranked, key=lambda item: (-item[0], item[1]))
    selected = sorted(chosen[:max_sentences], key=lambda item: item[1])
    return [item[2] for item in selected]

def main():
    if not SOURCE.exists():
        print("Missing output/fetched_page.json")
        print('Run: python ginne_brain.py fetch "HTTPS_URL"')
        return

    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    title = data.get("title", "Untitled page")
    url = data.get("url", "")
    content = data.get("text_preview", "")

    points = summarize(content)

    lines = [
        "# Ginne AI Summary",
        "",
        f"**Title:** {title}",
        f"**Source:** {url}",
        "",
        "## Key extracted points",
        ""
    ]

    lines.extend(f"- {point}" for point in points)

    lines.extend(["", "## Beginner-friendly explanation", ""])
    lower_text = content.lower()

    if "dictreader" in lower_text and "dictwriter" in lower_text:
        lines.append(
            "- `DictReader` reads CSV rows as dictionaries, using column "
            "headers as keys; `DictWriter` writes dictionary data to CSV."
        )

    if "csv.reader" in lower_text or "reader (" in lower_text:
        lines.append(
            "- A CSV reader processes rows from a CSV file so Python can "
            "work with the values."
        )

    if "csv.writer" in lower_text or "writer (" in lower_text:
        lines.append(
            "- A CSV writer converts rows of data into CSV-formatted text."
        )

    if "newline=''" in lower_text or 'newline=""' in lower_text:
        lines.append(
            "- Python's documentation recommends opening CSV files with "
            "`newline=''` in relevant file operations."
        )

    lines.extend([
        "",
        "## Limitations",
        "",
        "This is an automatic extractive summary, not a verified AI analysis.",
        "Only the text saved in fetched_page.json was processed.",
        "Check the original source before relying on important facts.",
        ""
    ])

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("Summary created:", REPORT)
    print("Points extracted:", len(points))
    print("\nPreview:\n")
    print("\n".join(f"- {p}" for p in points[:3]))

if __name__ == "__main__":
    main()
