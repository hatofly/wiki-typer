#!/usr/bin/env python3

import argparse
import gzip
import json
import re
import urllib.request
from pathlib import Path


DEFAULT_URL = (
    "https://kaikki.org/jawiktionary/"
    "raw-wiktextract-data.jsonl.gz"
)


def download_file(url: str, output: Path):
    """Download the Wiktionary JSONL.gz file."""
    print(f"Downloading:\n  {url}")
    print(f"          -> {output}")
    
    with urllib.request.urlopen(url) as response:
        total = response.headers.get("Content-Length")
        total = int(total) if total else None

        downloaded = 0

        with output.open("wb") as f:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break

                f.write(chunk)
                downloaded += len(chunk)

                if total:
                    percent = downloaded / total * 100
                    print(
                        f"\r  {downloaded / 1024 / 1024:.1f} MB"
                        f" / {total / 1024 / 1024:.1f} MB"
                        f" ({percent:.1f}%)",
                        end="",
                    )

    print("\nDownload complete.")


def normalize_category(category: str) -> str:
    """
    Normalize category strings so that
    'ja:物理学' and '物理学' can be compared.
    """
    category = category.strip()

    if ":" in category:
        prefix, value = category.split(":", 1)

        if prefix.lower() in {
            "ja",
            "japanese",
            "日本語",
        }:
            return value

    return category


def category_matches(categories, target: str) -> bool:
    """
    Check whether one of the sense categories matches target.
    """
    target = normalize_category(target)

    for category in categories or []:
        category = normalize_category(category)

        if category == target:
            return True

    return False


def is_japanese_entry(entry: dict) -> bool:
    """
    Keep entries whose Wiktionary language is Japanese.
    """
    return (
        entry.get("lang_code") == "ja"
        or entry.get("lang") == "Japanese"
    )


def is_japanese_text(text: str) -> bool:
    """
    Roughly determine whether a string contains Japanese characters.
    """
    return bool(
        re.search(
            r"[\u3040-\u309f\u30a0-\u30ff\u3400-\u4dbf\u4e00-\u9fff]",
            text,
        )
    )


def extract_reading(entry: dict) -> str:
    """
    Extract a Japanese reading.

    Wiktextract can contain several forms/sounds.
    We prefer hiragana/katakana readings.
    """

    candidates = []

    # forms
    for form in entry.get("forms", []):
        form_text = form.get("form", "")

        if not form_text:
            continue

        # Typical Japanese reading tags
        tags = set(form.get("tags", []))

        if (
            "hiragana" in tags
            or "katakana" in tags
            or "kana" in tags
        ):
            candidates.append(form_text)

    # sounds
    for sound in entry.get("sounds", []):
        ipa = sound.get("ipa", "")

        # Some Japanese entries have romanized data here,
        # but we don't use it as the primary reading.
        if is_japanese_text(ipa):
            candidates.append(ipa)

    # Remove duplicates while preserving order
    seen = set()

    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            return candidate

    return ""


def extract_english_translation(entry: dict) -> str:
    """
    Extract the first English translation.

    Wiktionary translations may contain:
      {
        "lang_code": "en",
        "lang": "English",
        "word": "..."
      }
    """

    translations = entry.get("translations", [])

    candidates = []

    for translation in translations:
        lang_code = translation.get("lang_code", "")
        lang = translation.get("lang", "")

        if lang_code == "en" or lang.lower() == "english":
            word = translation.get("word", "").strip()

            if word:
                candidates.append(word)

    # Remove duplicates
    candidates = list(dict.fromkeys(candidates))

    if candidates:
        return ", ".join(candidates[:3])

    return ""


def extract_description(entry: dict) -> str:
    """
    Extract a short description from the first available sense.
    """

    descriptions = []

    for sense in entry.get("senses", []):
        for gloss in sense.get("glosses", []):
            gloss = gloss.strip()

            if gloss:
                descriptions.append(gloss)

    # Remove duplicates while preserving order
    descriptions = list(dict.fromkeys(descriptions))

    if not descriptions:
        return ""

    # Use the first few definitions.
    return " / ".join(descriptions[:2])


def extract_entry(entry: dict, target_category: str):
    """
    Convert one Wiktextract entry into our simplified format.
    """

    if not is_japanese_entry(entry):
        return None

    term = entry.get("word", "").strip()

    if not term:
        return None

    matched_categories = []

    for sense in entry.get("senses", []):
        for category in sense.get("categories", []):
            category_normalized = normalize_category(category)

            if category_normalized == normalize_category(target_category):
                matched_categories.append(category_normalized)

    if not matched_categories:
        return None

    reading = extract_reading(entry)
    english = extract_english_translation(entry)
    description = extract_description(entry)

    # Require at least a term and description.
    if not description:
        return None

    return {
        "term": term,
        "reading": reading,
        "english": english,
        "description": description,
        "category": normalize_category(target_category),
    }


def process_jsonl(
    input_path: Path,
    output_path: Path,
    target_category: str,
):
    """
    Stream-process the JSONL file.

    The entire ~400 MB Wiktionary dataset is never loaded
    into memory at once.
    """

    results = []

    print(f"Processing category: {target_category}")

    with gzip.open(input_path, "rt", encoding="utf-8") as f:

        for line_number, line in enumerate(f, start=1):

            line = line.strip()

            if not line:
                continue

            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                print(
                    f"Warning: invalid JSON at line {line_number}",
                )
                continue

            result = extract_entry(
                entry,
                target_category,
            )

            if result is not None:
                results.append(result)

            if line_number % 100_000 == 0:
                print(
                    f"  processed {line_number:,} entries"
                    f" / found {len(results):,}"
                )

    # Remove duplicate terms.
    unique = {}

    for result in results:
        key = (
            result["term"],
            result["reading"],
        )

        if key not in unique:
            unique[key] = result

    results = list(unique.values())

    results.sort(
        key=lambda x: (
            x["term"],
            x["reading"],
        )
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            results,
            f,
            ensure_ascii=False,
            indent=2,
        )

    print()
    print("Done!")
    print(f"  Entries: {len(results):,}")
    print(f"  Output:  {output_path}")


def main():

    parser = argparse.ArgumentParser(
        description=(
            "Extract Japanese scientific terms from "
            "Wiktionary/Wiktextract data."
        )
    )

    parser.add_argument(
        "--category",
        required=True,
        help="Wiktionary category to extract.",
    )

    parser.add_argument(
        "--input",
        type=Path,
        default=Path("jawiktionary.jsonl.gz"),
        help="Path to Wiktextract JSONL.gz.",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("terms.json"),
        help="Output JSON path.",
    )

    parser.add_argument(
        "--download",
        action="store_true",
        help="Download the latest Japanese Wiktionary dump first.",
    )

    parser.add_argument(
        "--url",
        default=DEFAULT_URL,
        help="Wiktextract JSONL.gz URL.",
    )

    args = parser.parse_args()

    if args.download or not args.input.exists():

        download_file(
            args.url,
            args.input,
        )

    process_jsonl(
        args.input,
        args.output,
        args.category,
    )


if __name__ == "__main__":
    main()