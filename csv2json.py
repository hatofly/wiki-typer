#!/usr/bin/env python3
"""
CSV ディレクトリ内の *.csv ファイル(json_to_csv.py で出力した形式)を
同名の *.json ファイルに変換し、JSON ディレクトリに出力するスクリプト。

CSVの列: term, reading, english, description, category
  - term はそのまま文字列として出力
  - reading / english / description / category は "; " 区切りの文字列を
    リストに戻して出力する(空セルは空リストになる)

出力JSONの1要素の例:
{
    "term": "hoge",
    "reading": ["ほげ"],
    "english": ["hoge"],
    "description": ["ふが"],
    "category": ["ぴよ"]
}

使い方:
    python csv_to_json.py [CSVディレクトリ] [JSONディレクトリ]

引数を省略した場合はカレントディレクトリ直下の "CSV" と "JSON" を使用する。
"""

import csv
import json
import sys
from pathlib import Path

# リスト形式のセルを分割する際の区切り文字(json_to_csv.py と揃えること)
LIST_SEP = "; "

# リストとして扱う列
LIST_FIELDS = ["reading", "english", "description", "category"]

# term はリストにしない単一値の列
SCALAR_FIELDS = ["term"]


def cell_to_list(value: str):
    """"a; b; c" のような文字列をリストに戻す。空文字は空リストにする"""
    if value is None or value == "":
        return []
    return [v.strip() for v in value.split(LIST_SEP)]


def convert_file(csv_path: Path, json_path: Path):
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        entries = []
        for row in reader:
            entry = {}
            for field in SCALAR_FIELDS:
                entry[field] = row.get(field, "") or ""
            for field in LIST_FIELDS:
                entry[field] = cell_to_list(row.get(field, ""))
            entries.append(entry)

    json_path.parent.mkdir(parents=True, exist_ok=True)
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main():
    csv_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("CSV")
    json_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("JSON")

    if not csv_dir.is_dir():
        print(f"エラー: CSVディレクトリが見つかりません: {csv_dir}", file=sys.stderr)
        sys.exit(1)

    csv_files = sorted(csv_dir.glob("*.csv"))
    if not csv_files:
        print(f"警告: {csv_dir} に .csv ファイルが見つかりませんでした。")
        return

    json_dir.mkdir(parents=True, exist_ok=True)

    for csv_path in csv_files:
        json_path = json_dir / (csv_path.stem + ".json")
        try:
            convert_file(csv_path, json_path)
            print(f"変換完了: {csv_path.name} -> {json_path}")
        except Exception as e:
            print(f"エラー ({csv_path.name}): {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
