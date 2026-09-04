# -*- coding: utf-8 -*-
"""
v1.0 PDF氏名を既存DATAへ結合
- 追加: 空白除去・常用漢字ゆれ・ふりがな補助マッチ
- 継承: DATA の id/n/r
- 政治ポスト（大臣・副大臣・大臣政務官）はキャリア照合から除外
"""
from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE_DIR))
from lib.common import canon_kanji, canon_yomi, dump_json, is_political_post  # noqa: E402


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def build_indexes(data: list[dict]):
    by_name: dict[str, list[dict]] = defaultdict(list)
    by_yomi: dict[str, list[dict]] = defaultdict(list)
    for d in data:
        kn = canon_kanji(d.get("n") or "")
        ky = canon_yomi(d.get("r") or "")
        if kn:
            by_name[kn].append(d)
        if ky:
            by_yomi[ky].append(d)
    return by_name, by_yomi


def match_one(name_c: str, yomi_c: str, by_name, by_yomi) -> tuple[dict | None, str]:
    kn = canon_kanji(name_c)
    ky = canon_yomi(yomi_c)
    hits = by_name.get(kn) or []
    if len(hits) == 1:
        return hits[0], "name"
    if len(hits) > 1:
        if ky:
            sub = [h for h in hits if canon_yomi(h.get("r") or "") == ky]
            if len(sub) == 1:
                return sub[0], "name+yomi"
        return None, "ambiguous_name"
    if ky:
        yhits = by_yomi.get(ky) or []
        if len(yhits) == 1:
            return yhits[0], "yomi"
        if len(yhits) > 1:
            return None, "ambiguous_yomi"
    return None, "unmatched"


def main(out_dir: Path) -> None:
    data = load_json(out_dir / "data_filled.json")
    extracted = load_json(out_dir / "pdf_extract.json")
    by_name, by_yomi = build_indexes(data)

    matched_rows = []
    unmatched_rows = []
    political_rows = []

    for row in extracted["rows"]:
        rec = {
            "file": row["file"],
            "post_raw": row["post_raw"],
            "name_raw": row["name_raw"],
            "yomi_raw": row["yomi_raw"],
            "name_compact": row["name_compact"],
            "yomi_compact": row["yomi_compact"],
        }
        if is_political_post(row["post_raw"]):
            rec["kind"] = "political"
            political_rows.append(rec)
            continue
        hit, how = match_one(row["name_compact"], row["yomi_compact"], by_name, by_yomi)
        if hit:
            rec.update(
                {
                    "kind": "matched",
                    "how": how,
                    "id": hit["id"],
                    "n": hit["n"],
                    "y": hit.get("y") or "",
                    "r": hit.get("r") or "",
                }
            )
            matched_rows.append(rec)
        else:
            rec.update({"kind": how, "id": "", "n": "", "y": "", "r": ""})
            unmatched_rows.append(rec)

    dump_json(
        out_dir / "match_result.json",
        {
            "matched": matched_rows,
            "unmatched": unmatched_rows,
            "political": political_rows,
            "stats": {
                "pdf_rows": len(extracted["rows"]),
                "matched": len(matched_rows),
                "unmatched": len(unmatched_rows),
                "political": len(political_rows),
            },
        },
        indent=None,
    )

    def write_csv(path, rows, fields):
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)

    fields_m = [
        "file",
        "post_raw",
        "name_raw",
        "yomi_raw",
        "how",
        "id",
        "n",
        "y",
        "r",
    ]
    write_csv(out_dir / "matched.csv", matched_rows, fields_m)
    write_csv(
        out_dir / "unmatched.csv",
        unmatched_rows,
        ["file", "post_raw", "name_raw", "yomi_raw", "kind", "name_compact", "yomi_compact"],
    )
    write_csv(
        out_dir / "political.csv",
        political_rows,
        ["file", "post_raw", "name_raw", "yomi_raw", "name_compact"],
    )
    print(
        "matched",
        len(matched_rows),
        "unmatched",
        len(unmatched_rows),
        "political",
        len(political_rows),
    )


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    main(Path(args.out))
