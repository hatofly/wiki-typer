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


# ----------------------------------------------------------------------
# Category handling
# ----------------------------------------------------------------------

def normalize_category(category: str) -> str:
    """
    Normalize category names.

    Examples:
        日本語 物理学
        日本語_物理学
        ja:物理学
        物理学

    -> 物理学
    """

    if not category:
        return ""

    category = category.strip()

    # Wiktionary category names may use spaces or underscores.
    category = re.sub(r"[\s_]+", " ", category)

    # Remove language prefix.
    prefixes = (
        "日本語 ",
        "Japanese ",
        "ja:",
        "ja ",
    )

    for prefix in prefixes:
        if category.startswith(prefix):
            category = category[len(prefix):]
            break

    return category.strip()


def category_matches(category: str, target: str) -> bool:
    """
    Compare categories after normalization.
    """

    return (
        normalize_category(category)
        == normalize_category(target)
    )


# ----------------------------------------------------------------------
# Japanese text detection
# ----------------------------------------------------------------------

HIRAGANA_RE = re.compile(r"^[ぁ-ゖー]+$")
KATAKANA_RE = re.compile(r"^[ァ-ヺー]+$")


def is_hiragana(text: str) -> bool:
    return bool(HIRAGANA_RE.fullmatch(text))


def is_katakana(text: str) -> bool:
    return bool(KATAKANA_RE.fullmatch(text))


def is_kana(text: str) -> bool:
    """
    True if the entire string consists of hiragana/katakana.
    """

    return is_hiragana(text) or is_katakana(text)


# ----------------------------------------------------------------------
# Reading extraction
# ----------------------------------------------------------------------

def extract_reading(entry: dict) -> str:
    """
    Extract Japanese reading from forms.

    We prefer:
        - hiragana
        - katakana

    and ignore things such as:
        - ソウ
        - ショウ
        - transliteration of kanji

    because these are often on'yomi / kun'yomi labels rather
    than the actual kana reading of the word.

    Example:
        重力子 -> じゅうりょくし
        酸     -> (no reliable kana reading from forms)
    """

    candidates = []

    for form in entry.get("forms", []):
        value = form.get("form", "").strip()

        if not value:
            continue

        # Actual kana spelling
        if is_kana(value):
            candidates.append(value)

    # Remove duplicates while preserving order.
    candidates = list(dict.fromkeys(candidates))

    if not candidates:
        return ""

    # Prefer hiragana.
    hiragana = [
        x for x in candidates
        if is_hiragana(x)
    ]

    if hiragana:
        return hiragana[0]

    return candidates[0]


# ----------------------------------------------------------------------
# English translation
# ----------------------------------------------------------------------

def extract_english_translation(entry: dict) -> str:
    """
    Extract English translations.

    Returns up to three unique English translations.
    """

    candidates = []

    for translation in entry.get("translations", []):

        lang_code = translation.get(
            "lang_code",
            "",
        )

        lang = translation.get(
            "lang",
            "",
        )

        if (
            lang_code == "en"
            or lang.lower() in {
                "english",
                "英語",
            }
        ):
            word = translation.get(
                "word",
                "",
            ).strip()

            if word:
                candidates.append(word)

    # Deduplicate
    candidates = list(dict.fromkeys(candidates))

    return ", ".join(candidates[:3])


# ----------------------------------------------------------------------
# Sense extraction
# ----------------------------------------------------------------------

def find_matching_senses(
    entry: dict,
    target_category: str,
):
    """
    Find senses whose categories contain target_category.

    IMPORTANT:
    The gloss must be taken from the SAME sense that contains
    the matching category.

    This fixes the problem illustrated by:

        相

    where only the 7th sense belongs to physics.
    """

    matching_senses = []

    for sense in entry.get("senses", []):

        categories = sense.get(
            "categories",
            [],
        )

        if any(
            category_matches(
                category,
                target_category,
            )
            for category in categories
        ):
            matching_senses.append(sense)

    return matching_senses


def extract_description_from_senses(
    senses: list,
) -> str:
    """
    Extract descriptions from matching senses.
    """

    descriptions = []

    for sense in senses:

        for gloss in sense.get(
            "glosses",
            [],
        ):

            gloss = gloss.strip()

            if gloss:
                descriptions.append(gloss)

    # Remove duplicates while preserving order.
    descriptions = list(
        dict.fromkeys(descriptions)
    )

    if not descriptions:
        return ""

    # Join multiple meanings.
    return " / ".join(descriptions)


# ----------------------------------------------------------------------
# Entry extraction
# ----------------------------------------------------------------------

def extract_entry(
    entry: dict,
    target_category: str,
):
    """
    Convert a Wiktextract entry into the simplified format.
    """

    # Japanese entries only.
    if entry.get("lang_code") != "ja":
        return None

    term = entry.get(
        "word",
        "",
    ).strip()

    if not term:
        return None

    # Find senses belonging to the requested category.
    matching_senses = find_matching_senses(
        entry,
        target_category,
    )

    if not matching_senses:
        return None

    description = extract_description_from_senses(
        matching_senses
    )

    # Ignore entries with no usable definition.
    if not description:
        return None

    reading = extract_reading(entry)

    english = extract_english_translation(entry)

    return {
        "term": term,
        "reading": reading,
        "english": english,
        "description": description,
        "category": normalize_category(
            target_category
        ),
    }


# ----------------------------------------------------------------------
# Download
# ----------------------------------------------------------------------

def download_file(
    url: str,
    output: Path,
):
    """
    Download Wiktextract JSONL.gz.
    """

    print(f"Downloading:")
    print(f"  {url}")
    print(f"  -> {output}")

    with urllib.request.urlopen(url) as response:

        total = response.headers.get(
            "Content-Length"
        )

        total = (
            int(total)
            if total
            else None
        )

        downloaded = 0

        with output.open("wb") as f:

            while True:

                chunk = response.read(
                    1024 * 1024
                )

                if not chunk:
                    break

                f.write(chunk)

                downloaded += len(chunk)

                if total:

                    percent = (
                        downloaded
                        / total
                        * 100
                    )

                    print(
                        f"\r  "
                        f"{downloaded / 1024 / 1024:.1f} MB"
                        f" / "
                        f"{total / 1024 / 1024:.1f} MB"
                        f" "
                        f"({percent:.1f}%)",
                        end="",
                    )

    print()
    print("Download complete.")


# ----------------------------------------------------------------------
# JSONL processing
# ----------------------------------------------------------------------

def process_jsonl(
    input_path: Path,
    output_path: Path,
    target_category: str,
):
    """
    Process Wiktextract JSONL.gz line by line.

    The complete dataset is never loaded into memory.
    """

    results = []

    print()
    print(
        f"Target category: "
        f"{normalize_category(target_category)}"
    )
    print()

    with gzip.open(
        input_path,
        "rt",
        encoding="utf-8",
    ) as f:

        for line_number, line in enumerate(
            f,
            start=1,
        ):

            line = line.strip()

            if not line:
                continue

            try:
                entry = json.loads(line)

            except json.JSONDecodeError:

                print(
                    f"Warning: invalid JSON "
                    f"at line {line_number}"
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
                    f"  processed "
                    f"{line_number:,} entries"
                    f" / found "
                    f"{len(results):,}"
                )

    # ------------------------------------------------------------------
    # Deduplicate
    # ------------------------------------------------------------------

    unique = {}

    for result in results:

        key = (
            result["term"],
            result["reading"],
            result["description"],
        )

        if key not in unique:
            unique[key] = result

    results = list(
        unique.values()
    )

    # Sort alphabetically by term.
    results.sort(
        key=lambda x: (
            x["term"],
            x["reading"],
        )
    )

    # ------------------------------------------------------------------
    # Write JSON
    # ------------------------------------------------------------------

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
    print(
        f"  Entries: "
        f"{len(results):,}"
    )
    print(
        f"  Output:  "
        f"{output_path}"
    )


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Extract Japanese terms from "
            "Wiktionary/Wiktextract data."
        )
    )

    parser.add_argument(
        "--category",
        required=True,
        help=(
            "Wiktionary category, "
            "e.g. '物理学'"
        ),
    )

    parser.add_argument(
        "--input",
        type=Path,
        default=Path(
            "jawiktionary.jsonl.gz"
        ),
        help=(
            "Path to Wiktextract JSONL.gz."
        ),
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "terms.json"
        ),
        help="Output JSON path.",
    )

    parser.add_argument(
        "--download",
        action="store_true",
        help=(
            "Download the latest "
            "Japanese Wiktionary dump first."
        ),
    )

    parser.add_argument(
        "--url",
        default=DEFAULT_URL,
        help="Wiktextract JSONL.gz URL.",
    )

    args = parser.parse_args()

    # Download if requested or if file doesn't exist.
    if (
        args.download
        or not args.input.exists()
    ):

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