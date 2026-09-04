# -*- coding: utf-8 -*-
"""
v1.0 財務省幹部名簿PDF抽出
- 追加: original_pdf 全件（職名/氏名/ふりがな/基準日/年度）
- 継承: なし（新規）。表抽出を優先し、空行・『同』・兼務行を結合
- 更新: 令和8年8月7日現在 meiboR080807 を最新として扱う
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

import pdfplumber

CODE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE_DIR))
from lib.common import (  # noqa: E402
    PDF_DIR,
    compact_text,
    dump_json,
    fy_label_from_date,
    nfkc,
    parse_filename_date,
    parse_text_date,
)


HEADER_TOKENS = {"職名", "氏名", "ふりがな", "職名氏名ふりがな"}


def clean_cell(v) -> str:
    if v is None:
        return ""
    s = nfkc(str(v)).replace("\n", "").strip()
    s = re.sub(r"[ \t]+", " ", s)
    return s


def is_header_row(post: str, name: str, yomi: str) -> bool:
    blob = compact_text(post + name + yomi)
    return blob in HEADER_TOKENS or blob.startswith("財務省幹部名簿")


def extract_pdf(path: Path) -> dict:
    rows_out = []
    text_all = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            text_all.append(page.extract_text() or "")
            tables = page.extract_tables() or []
            for table in tables:
                pending_posts: list[str] = []
                last_post = ""
                for raw in table:
                    if not raw:
                        continue
                    cells = [clean_cell(c) for c in raw]
                    while len(cells) < 3:
                        cells.append("")
                    post, name, yomi = cells[0], cells[1], cells[2]
                    if is_header_row(post, name, yomi):
                        continue
                    if not post and not name:
                        continue
                    if post:
                        pending_posts.append(post)
                    if not name:
                        continue
                    joined = "".join(pending_posts) if pending_posts else last_post
                    joined = joined.strip()
                    if compact_text(joined) in {"同", "同（同）"} or joined.startswith("同"):
                        joined = last_post
                    # 『同 （同）』を正規化
                    if compact_text(joined).startswith("同"):
                        joined = last_post
                    if joined:
                        last_post = joined
                    rows_out.append(
                        {
                            "file": path.name,
                            "post_raw": joined,
                            "name_raw": name,
                            "yomi_raw": yomi,
                            "name_compact": compact_text(name),
                            "yomi_compact": compact_text(yomi),
                        }
                    )
                    pending_posts = []
    blob = "\n".join(text_all)
    d = parse_filename_date(path.name) or parse_text_date(blob)
    fy = fy_label_from_date(d) if d else ""
    return {
        "file": path.name,
        "as_of": d.isoformat() if d else "",
        "fy": fy,
        "n_rows": len(rows_out),
        "rows": rows_out,
        "title_text": (text_all[0][:200] if text_all else ""),
    }


def main(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(PDF_DIR.glob("meiboR*.pdf"))
    all_rows = []
    meta = []
    for pdf in pdfs:
        rec = extract_pdf(pdf)
        meta.append({k: rec[k] for k in ("file", "as_of", "fy", "n_rows")})
        all_rows.extend(rec["rows"])
        print(pdf.name, rec["as_of"], rec["fy"], rec["n_rows"])
    dump_json(out_dir / "pdf_extract.json", {"files": meta, "rows": all_rows}, indent=None)
    dump_json(out_dir / "pdf_files.json", meta)
    with (out_dir / "pdf_extract.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["file", "post_raw", "name_raw", "yomi_raw", "name_compact", "yomi_compact"],
        )
        w.writeheader()
        w.writerows(all_rows)
    print("pdfs", len(pdfs), "rows", len(all_rows))


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    main(Path(args.out))
