#!/usr/bin/env python3

import argparse
import gzip
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path


# ============================================================
# Configuration
# ============================================================

DEFAULT_URL = (
    "https://kaikki.org/jawiktionary/"
    "raw-wiktextract-data.jsonl.gz"
)

WIKTIONARY_API = (
    "https://ja.wiktionary.org/w/api.php"
)


# ============================================================
# Category normalization
# ============================================================

def normalize_category(category: str) -> str:
    """
    Normalize Wiktionary category names.

    Examples:

        日本語 物理学
        日本語_物理学
        ja:物理学
        物理学

    are normalized to:

        物理学
    """

    if not category:
        return ""

    category = category.strip()

    # Underscore and whitespace are equivalent for
    # MediaWiki category names.
    category = re.sub(r"[\s_]+", " ", category)

    prefixes = (
        "日本語 ",
        "Japanese ",
        "ja:",
        "ja ",
        "カテゴリ:"
    )

    for prefix in prefixes:
        if category.startswith(prefix):
            category = category[len(prefix):]
            break

    return category.strip()


def category_matches(
    category: str,
    target: str,
) -> bool:

    return (
        normalize_category(category)
        == normalize_category(target)
    )


# ============================================================
# Wiktionary category API
# ============================================================

def api_request(params: dict) -> dict:
    """
    Perform a request to the Japanese Wiktionary API.
    """

    params = {
        **params,
        "action": "query",
        "format": "json",
        "formatversion": "2",
    }

    query = urllib.parse.urlencode(
        params,
        doseq=True,
    )

    url = (
        WIKTIONARY_API
        + "?"
        + query
    )

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent":
                "ScientificTypingTermExtractor/1.0"
        },
    )

    with urllib.request.urlopen(request) as response:
        return json.loads(
            response.read()
        )


def get_subcategories(
    category: str,
) -> list[str]:
    """
    Get all direct subcategories of a category.

    Pagination via cmcontinue is handled automatically.
    """

    category_title = (
        "Category:"
        + category
    )

    subcategories = []

    continue_token = None

    while True:

        params = {
            "list": "categorymembers",
            "cmtitle": category_title,
            "cmtype": "subcat",
            "cmlimit": "500",
        }

        if continue_token:
            params["cmcontinue"] = (
                continue_token
            )

        data = api_request(params)

        members = (
            data
            .get("query", {})
            .get("categorymembers", [])
        )

        for member in members:

            title = member.get(
                "title",
                "",
            )

            if title.startswith(
                "Category:"
            ):
                title = title[
                    len("Category:"):
                ]

            if title:
                subcategories.append(
                    title
                )

        continuation = data.get(
            "continue"
        )

        if not continuation:
            break

        continue_token = continuation.get(
            "cmcontinue"
        )

        if not continue_token:
            break

    return subcategories

def is_language_category(
    category: str,
    parent_category: str,
) -> bool:
    """
    Return True if category looks like:

        <language> <parent_category>

    Examples:

        イタリア語 物理学
        英語 物理学
        ドイツ語 力学

    These are language-specific categories and should not
    be followed during scientific-category recursion.
    """

    category = normalize_category(category)
    parent_category = normalize_category(parent_category)

    if not category.endswith(
        " " + parent_category
    ):
        return False

    prefix = category[
        :-(len(parent_category) + 1)
    ].strip()

    if not prefix:
        return False

    # Japanese Wiktionary language names.
    #
    # This is deliberately somewhat conservative rather than
    # trying to enumerate every possible language.
    language_names = (
        "語",
        "語の",
        "インターリングア",
        "エスペラント",
        "トク・ピシン",
        "ロジバン"
    )

    # prefixに言語名が含まれていたらTrueを返す
    for name in language_names:
        if name in prefix:
            return True

    return False

def collect_categories(
    root_category: str,
    delay: float = 0.1,
) -> set[str]:

    root = normalize_category(
        root_category
    )

    visited = set()
    queue = [
        (root, None)
    ]

    while queue:

        category, parent = queue.pop(0)

        if category in visited:
            continue

        visited.add(category)

        print(
            f"  category: {category}"
        )

        try:
            children = get_subcategories(
                category
            )

        except Exception as e:

            print(
                f"    WARNING: failed to "
                f"retrieve subcategories: {e}"
            )

            continue

        for child in children:

            normalized = normalize_category(
                child
            )

            # ------------------------------------------------
            # Exclude language-specific categories
            # ------------------------------------------------

            if is_language_category(
                normalized,
                category,
            ):
                print(
                    f"    skip: {normalized}"
                )
                continue

            if normalized not in visited:

                queue.append(
                    (
                        normalized,
                        category,
                    )
                )

        if delay > 0:
            time.sleep(delay)

    return visited

# ============================================================
# Japanese text / kana
# ============================================================

HIRAGANA_RE = re.compile(
    r"^[ぁ-ゖー]+$"
)

KATAKANA_RE = re.compile(
    r"^[ァ-ヺー]+$"
)


def is_hiragana(text: str) -> bool:
    return bool(
        HIRAGANA_RE.fullmatch(text)
    )


def is_katakana(text: str) -> bool:
    return bool(
        KATAKANA_RE.fullmatch(text)
    )


def is_kana(text: str) -> bool:
    return (
        is_hiragana(text)
        or is_katakana(text)
    )


# ============================================================
# Reading extraction
# ============================================================

def extract_readings(
    entry: dict,
) -> list[str]:
    """
    Extract possible kana readings.

    Priority:

        1. forms[].form containing hiragana
        2. forms[].form containing katakana
        3. sounds[].other containing kana

    Multiple readings are preserved.
    """

    hiragana = []
    katakana = []
    sound_other = []

    # --------------------------------------------------------
    # forms
    # --------------------------------------------------------

    for form in entry.get(
        "forms",
        [],
    ):

        value = form.get(
            "form",
            "",
        ).strip()

        if not value:
            continue

        if is_hiragana(value):
            hiragana.append(value)

        elif is_katakana(value):
            katakana.append(value)

    # --------------------------------------------------------
    # sounds
    # --------------------------------------------------------

    for sound in entry.get(
        "sounds",
        [],
    ):

        value = sound.get(
            "other",
            "",
        ).strip()

        if not value:
            continue

        if is_kana(value):
            sound_other.append(value)

    # --------------------------------------------------------
    # Combine according to priority.
    # --------------------------------------------------------

    result = []

    for values in (
        hiragana,
        katakana,
        sound_other,
    ):

        for value in values:

            if value not in result:
                result.append(value)

    return result


# ============================================================
# English translation
# ============================================================

def extract_english(
    entry: dict,
) -> list[str]:
    """
    Extract English translations.
    """

    result = []

    for translation in entry.get(
        "translations",
        [],
    ):

        lang_code = translation.get(
            "lang_code",
            "",
        )

        lang = translation.get(
            "lang",
            "",
        )

        if not (
            lang_code == "en"
            or lang.lower() in {
                "english",
                "英語",
            }
        ):
            continue

        word = translation.get(
            "word",
            "",
        ).strip()

        if (
            word
            and word not in result
        ):
            result.append(word)

    return result


# ============================================================
# Sense extraction
# ============================================================

def get_matching_senses(
    entry: dict,
    target_categories: set[str],
):
    """
    Return senses whose categories belong to the
    recursively collected target category tree.
    """

    matching = []

    for sense in entry.get(
        "senses",
        [],
    ):

        categories = sense.get(
            "categories",
            [],
        )

        matched_categories = []

        for category in categories:

            normalized = normalize_category(
                category
            )

            if normalized in target_categories:
                matched_categories.append(
                    normalized
                )

        if matched_categories:

            matching.append(
                (
                    sense,
                    matched_categories,
                )
            )

    return matching


def extract_descriptions(
    matching_senses,
) -> tuple[list[str], list[str]]:
    """
    Extract glosses and their corresponding categories.

    Returns:

        descriptions
        categories
    """

    descriptions = []
    categories = []

    for sense, sense_categories in (
        matching_senses
    ):

        glosses = sense.get(
            "glosses",
            [],
        )

        if not glosses:
            continue

        for gloss in glosses:

            gloss = gloss.strip()

            if not gloss:
                continue

            if gloss not in descriptions:

                descriptions.append(
                    gloss
                )

            for category in (
                sense_categories
            ):

                if category not in categories:
                    categories.append(
                        category
                    )

    return (
        descriptions,
        categories,
    )


# ============================================================
# Entry extraction
# ============================================================

def extract_entry(
    entry: dict,
    target_categories: set[str],
):
    """
    Convert a Wiktextract entry into our
    simplified JSON format.
    """

    # Japanese entries only.
    if entry.get(
        "lang_code"
    ) != "ja":
        return None

    term = entry.get(
        "word",
        "",
    ).strip()

    if not term:
        return None

    # --------------------------------------------------------
    # Find category-matching senses.
    # --------------------------------------------------------

    matching_senses = get_matching_senses(
        entry,
        target_categories,
    )

    if not matching_senses:
        return None

    # --------------------------------------------------------
    # Extract only descriptions from
    # category-matching senses.
    # --------------------------------------------------------

    (
        descriptions,
        categories,
    ) = extract_descriptions(
        matching_senses
    )

    if not descriptions:
        return None

    # --------------------------------------------------------
    # Other fields
    # --------------------------------------------------------

    readings = extract_readings(
        entry
    )

    english = extract_english(
        entry
    )

    return {
        "term": term,
        "reading": readings,
        "english": english,
        "description": descriptions,
        "category": categories,
    }


# ============================================================
# Download
# ============================================================

def download_file(
    url: str,
    output: Path,
):
    """
    Download Wiktextract JSONL.gz.
    """

    print("Downloading:")
    print(f"  {url}")
    print(f"  -> {output}")

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent":
                "ScientificTypingTermExtractor/1.0"
        },
    )

    with urllib.request.urlopen(
        request
    ) as response:

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
                        f" ({percent:.1f}%)",
                        end="",
                    )

    print()
    print("Download complete.")


# ============================================================
# JSONL processing
# ============================================================

def process_jsonl(
    input_path: Path,
    output_path: Path,
    target_categories: set[str],
):
    """
    Stream-process the Wiktextract JSONL.gz file.
    """

    results = []

    print()
    print(
        f"Processing "
        f"{len(target_categories)} categories..."
    )

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
                entry = json.loads(
                    line
                )

            except json.JSONDecodeError:

                print(
                    f"WARNING: invalid JSON "
                    f"at line {line_number}"
                )

                continue

            result = extract_entry(
                entry,
                target_categories,
            )

            if result is not None:
                results.append(
                    result
                )

            if (
                line_number % 100_000
                == 0
            ):

                print(
                    f"  processed "
                    f"{line_number:,}"
                    f" / found "
                    f"{len(results):,}"
                )

    # --------------------------------------------------------
    # Deduplicate
    # --------------------------------------------------------

    unique = {}

    for result in results:

        key = (
            result["term"],
            tuple(result["reading"]),
            tuple(result["description"]),
        )

        if key not in unique:
            unique[key] = result

    results = list(
        unique.values()
    )

    # --------------------------------------------------------
    # Sort
    # --------------------------------------------------------

    results.sort(
        key=lambda x: (
            x["term"],
            x["reading"],
        )
    )

    # --------------------------------------------------------
    # Write JSON
    # --------------------------------------------------------

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
        f"  Output: "
        f"{output_path}"
    )


# ============================================================
# Main
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Extract Japanese scientific "
            "terms from Wiktionary."
        )
    )

    parser.add_argument(
        "--category",
        required=True,
        help=(
            "Root category, "
            "e.g. 物理学"
        ),
    )

    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help=(
            "Do not search subcategories."
        ),
    )

    parser.add_argument(
        "--input",
        type=Path,
        default=Path(
            "jawiktionary.jsonl.gz"
        ),
        help=(
            "Path to Wiktextract "
            "JSONL.gz."
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
            "Wiktionary dump."
        ),
    )

    parser.add_argument(
        "--url",
        default=DEFAULT_URL,
        help="Wiktextract JSONL.gz URL.",
    )

    args = parser.parse_args()

    # --------------------------------------------------------
    # Download
    # --------------------------------------------------------

    if (
        args.download
        or not args.input.exists()
    ):

        download_file(
            args.url,
            args.input,
        )

    # --------------------------------------------------------
    # Collect categories
    # --------------------------------------------------------

    print()
    print(
        f"Collecting categories under "
        f"'{args.category}'..."
    )

    root = normalize_category(
        args.category
    )

    if args.no_recursive:

        target_categories = {
            root
        }

    else:

        target_categories = (
            collect_categories(root)
        )

    print()
    print(
        f"Found "
        f"{len(target_categories)} "
        f"categories."
    )

    # --------------------------------------------------------
    # Process dump
    # --------------------------------------------------------
    print(f"Target categories: {target_categories}")
    process_jsonl(
        args.input,
        args.output,
        target_categories,
    )


if __name__ == "__main__":
    main()