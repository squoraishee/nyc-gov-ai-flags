"""Build site/data.js from the scraped articles and Pangram results.

Run from the project folder:
    python3 site/build_data.py

Each release is split into paragraphs. A paragraph is marked when a flagged
passage from the detector starts inside it.
"""

import json
import re
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
SITE = PROJECT / "site"

SPANISH = {"el", "la", "los", "las", "de", "del", "que", "en", "y", "para", "con", "por", "una", "su", "sus", "alcalde"}
ENGLISH = {"the", "of", "and", "to", "in", "is", "for", "with", "that", "a", "on", "as", "by", "new"}
AGENCY = {"mayor": "Mayor's Office", "dot": "DOT", "dcla": "DCLA"}
FLAG_LABELS = {"AI-Generated", "AI-Assisted"}


def normalize(text):
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = text.replace("—", "-").replace("–", "-")
    return re.sub(r"\s+", " ", text).strip().lower()


def is_spanish(text):
    words = re.findall(r"[a-záéíóúñ]+", text.lower()[:4000])
    return sum(w in SPANISH for w in words) > 1.2 * sum(w in ENGLISH for w in words)


def split_paragraphs(text):
    return [p.strip() for p in text.split("\n\n") if p.strip()]


def build_release(source, article_file, result_file):
    article = json.loads(article_file.read_text(encoding="utf-8"))
    result = json.loads(result_file.read_text(encoding="utf-8"))

    paragraphs = []
    for text in split_paragraphs(article["text"]):
        paragraphs.append({"text": text, "flag": None, "score": None})

    # Match each flagged window to the paragraph where its opening words appear.
    for window in result.get("windows", []):
        if window.get("label") not in FLAG_LABELS:
            continue
        opening = normalize(window.get("text", ""))[:60]
        if len(opening) < 20:
            continue
        score = float(window.get("ai_assistance_score") or 0)
        for para in paragraphs:
            if opening in normalize(para["text"]):
                if para["score"] is None or score > para["score"]:
                    para["flag"] = window["label"]
                    para["score"] = round(score, 3)
                break

    ai = float(result.get("fraction_ai") or 0) + float(result.get("fraction_ai_assisted") or 0)
    return {
        "id": article_file.stem[:10],
        "source": source,
        "agency": AGENCY[source],
        "title": article["title"],
        "published": article["published"],
        "url": article["url"],
        "words": article["word_count"],
        "spanish": is_spanish(article["text"]),
        "headline": result.get("headline"),
        "ai_share": round(ai, 3),
        "flagged_paragraphs": sum(1 for p in paragraphs if p["flag"]),
        "paragraphs": paragraphs,
    }


def main():
    releases = []
    for result_file in sorted((PROJECT / "data" / "pangram").glob("*/*.json")):
        source = result_file.parent.name
        article_file = PROJECT / "data" / "articles" / source / result_file.name
        if article_file.exists():
            releases.append(build_release(source, article_file, result_file))
    releases.sort(key=lambda r: r["published"] or "", reverse=True)

    payload = "window.RELEASES = " + json.dumps(releases, ensure_ascii=False) + ";\n"
    (SITE / "data.js").write_text(payload, encoding="utf-8")
    flagged = sum(1 for r in releases if r["flagged_paragraphs"])
    print(f"wrote site/data.js: {len(releases)} releases, {flagged} with flagged paragraphs")


if __name__ == "__main__":
    main()
