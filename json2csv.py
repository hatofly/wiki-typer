#!/usr/bin/env python3
"""
JSON ディレクトリ内の *.json ファイル(それぞれ下記形式のオブジェクトの配列)を
同名の *.csv ファイルに変換し、CSV ディレクトリに出力するスクリプト。

入力JSONの1要素の例:
{
    "term": "hoge",
    "reading": ["ほげ"],
    "english": ["hoge"],
    "description": ["ふが"],
    "category": ["ぴよ"]
}

使い方:
    python json_to_csv.py [JSONディレクトリ] [CSVディレクトリ]

引数を省略した場合はカレントディレクトリ直下の "JSON" と "CSV" を使用する。
"""

import csv
import json
import sys
from pathlib import Path

# CSVの列名(出力順)
FIELDS = ["term", "reading", "english", "description", "category"]

# リスト形式の値を1つのセルにまとめる際の区切り文字
LIST_SEP = "; "


def normalize_cell(value):
    """値がリストなら区切り文字で連結した文字列に、それ以外はそのまま文字列化する"""
    if value is None:
        return ""
    if isinstance(value, list):
        return LIST_SEP.join(str(v) for v in value)
    return str(value)


def convert_file(json_path: Path, csv_path: Path):
    with json_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        # 万が一、配列ではなく単一オブジェクトだった場合にも対応
        data = [data]

    csv_path.parent.mkdir(parents=True, exist_ok=True)

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for entry in data:
            row = {field: normalize_cell(entry.get(field)) for field in FIELDS}
            writer.writerow(row)


def main():
    json_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("JSON")
    csv_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("CSV")

    if not json_dir.is_dir():
        print(f"エラー: JSONディレクトリが見つかりません: {json_dir}", file=sys.stderr)
        sys.exit(1)

    json_files = sorted(json_dir.glob("*.JSON"))
    if not json_files:
        print(f"警告: {json_dir} に .json ファイルが見つかりませんでした。")
        return

    csv_dir.mkdir(parents=True, exist_ok=True)

    for json_path in json_files:
        csv_path = csv_dir / (json_path.stem + ".csv")
        try:
            convert_file(json_path, csv_path)
            print(f"変換完了: {json_path.name} -> {csv_path}")
        except Exception as e:
            print(f"エラー ({json_path.name}): {e}", file=sys.stderr)


if __name__ == "__main__":
    main()