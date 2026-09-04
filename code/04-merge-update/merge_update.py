# -*- coding: utf-8 -*-
"""
v1.2 代表PDFでキャリア追記し、TL_DATA を再計算
- 追加: 令和4-8の政権名（代表日時点）、年表カラムに財務官
- 追加: 幹部名簿に載らない税関長等を CAREER_OVERRIDES で補完
- 継承: 既存 career は上書きしない。R5-R8は新規、R4は空欄のみ補充
- 新出氏名は unmatched のまま DATA に追加しない
"""
from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE_DIR))
from lib.common import (  # noqa: E402
    SRC_HTML,
    clean_post,
    dump_json,
    extract_js_literal,
    fy_fmt,
    fy_sort_key,
    is_political_post,
    nfkc,
    normalize_person,
    unify_display,
)


def is_zaimukan(post: str) -> bool:
    s = (post or "").replace(" ", "").replace("　", "")
    if "副財務官" in s or "財務官室" in s:
        return False
    return s == "財務官" or s.startswith("財務官")


ROLE_MATCHERS = {
    "事務次官": lambda p: "事務次官" in p,
    "財務官": is_zaimukan,
    "官房長": lambda p: ("官房長" in p) and ("次長" not in p),
    "主計局長": lambda p: ("主計局長" in p) and ("次長" not in p),
    "主税局長": lambda p: ("主税局長" in p) and ("次長" not in p),
    "文書課長": lambda p: "文書課長" in p,
}

TL_ROLES = ["政権", "財務大臣", "事務次官", "財務官", "官房長", "主計局長", "主税局長", "文書課長"]

# 代表PDF日付時点の内閣。既存表記（首相名＋内閣区分）に合わせる。
SEIKEN_FILL = {
    "令和４年度": "岸田文雄（第2次）",
    "令和５年度": "岸田文雄（第2次改造）",
    "令和６年度": "岸田文雄（第2次改造②）",
    "令和７年度": "石破茂（第2次）",
    "令和８年度": "高市早苗（第2次）",
}

NEW_FY_LABELS = ["令和５年度", "令和６年度", "令和７年度", "令和８年度"]
VERIFY_FY = {
    "令和２年度": date(2020, 8, 1),
    "令和３年度": date(2021, 8, 1),
    "令和４年度": date(2022, 8, 1),
}

# 財務省幹部名簿に税関長は載らない。代表PDF日時点の外局ポストを手補完する。
CAREER_OVERRIDES = [
    {"id": 1967, "fy": "令和８年度", "post": "東京税関長"},
]


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def rank_score(post: str) -> int:
    keys = [
        ("事務次官", 1),
        ("財務官", 2),
        ("官房長", 3),
        ("局長", 4),
        ("次長", 5),
        ("部長", 6),
        ("審議官", 7),
        ("参事官", 8),
        ("課長", 9),
    ]
    for k, s in keys:
        if k in post:
            return s
    return 50


def pick_primary_post(posts: list[str]) -> str:
    uniq = []
    seen = set()
    for p in posts:
        p = (p or "").strip()
        if not p or p in seen:
            continue
        seen.add(p)
        uniq.append(p)
    if not uniq:
        return ""
    uniq.sort(key=rank_score)
    return uniq[0]


def choose_rep_files(file_meta: list[dict]) -> dict[str, dict]:
    """FYラベル → 8月1日最近傍ファイル。"""
    by_fy: dict[str, list[dict]] = defaultdict(list)
    for m in file_meta:
        if m.get("fy") and m.get("as_of"):
            by_fy[m["fy"]].append(m)
    chosen = {}
    for fy, items in by_fy.items():
        # target Aug 1 of that FY
        fmt = fy_fmt(fy)
        western = int(fmt.split("_")[0]) if fmt else 2000
        target = date(western, 8, 1)

        def dist(m):
            d = date.fromisoformat(m["as_of"])
            return abs((d - target).days)

        items_sorted = sorted(items, key=dist)
        chosen[fy] = items_sorted[0]
    return chosen


def career_post_for_fy(person: dict, fy_substrs: list[str]) -> str:
    for c in person.get("career") or []:
        lab = c.get("年度") or ""
        if any(s in lab or s in nfkc(lab) for s in fy_substrs):
            return c.get("ポスト") or ""
    return ""


def rebuild_latest_fields(person: dict) -> None:
    career = person.get("career") or []
    career.sort(key=lambda c: fy_sort_key(c.get("年度") or ""), reverse=True)
    person["career"] = career
    person["cnt"] = len(career)
    if career:
        person["p"] = career[0].get("ポスト") or ""
        person["fy"] = career[0].get("年度") or ""
    else:
        person["p"] = ""
        person["fy"] = ""


def apply_career_overrides(people: dict[int, dict]) -> int:
    n = 0
    for ov in CAREER_OVERRIDES:
        person = people.get(ov["id"])
        if not person:
            continue
        fy = ov["fy"]
        post = clean_post(ov["post"])
        career = person.setdefault("career", [])
        existing = next((c for c in career if (c.get("年度") or "") == fy), None)
        if existing:
            existing["ポスト"] = post
        else:
            career.insert(0, {"年度": fy, "ポスト": post})
        rebuild_latest_fields(person)
        n += 1
    return n


def load_original_tl() -> dict:
    text = SRC_HTML.read_text(encoding="utf-8")
    script = text[text.find("<script>") + 8 :]
    raw = extract_js_literal(script, "const TL_DATA", "{", "}")
    return json.loads(raw)


def rebuild_tl(data: list[dict], daijin_by_fy: dict[str, str], orig_tl: dict) -> dict:
    years = list(orig_tl.get("years") or [])
    existing_raw = {y["raw"] for y in years}
    prepend = []
    for lab in ["令和８年度", "令和７年度", "令和６年度", "令和５年度", "令和４年度"]:
        if lab not in existing_raw:
            prepend.append({"raw": lab, "fmt": fy_fmt(lab)})
    years = prepend + years

    seiken = dict(orig_tl.get("seiken") or {})
    for fy, name in SEIKEN_FILL.items():
        if not (seiken.get(fy) or "").strip():
            seiken[fy] = name
    daijin = dict(orig_tl.get("daijin") or {})
    daijin.update({k: v for k, v in daijin_by_fy.items() if v})

    tl_map: dict[str, dict] = {}
    # start from original map so old years stay
    for y, posts in (orig_tl.get("map") or {}).items():
        tl_map[y] = posts

    by_id = {d["id"]: d for d in data}
    for person in data:
        for c in person.get("career") or []:
            fy = c.get("年度") or ""
            post = c.get("ポスト") or ""
            if not fy or not post:
                continue
            bucket = tl_map.setdefault(fy, {})
            for role, pred in ROLE_MATCHERS.items():
                if pred(post):
                    arr = bucket.setdefault(role, [])
                    rec = {"name": person["n"], "id": person["id"], "yf": person.get("yf") or ""}
                    if not any(x.get("id") == rec["id"] for x in arr):
                        arr.append(rec)

    return {
        "years": years,
        "roles": TL_ROLES,
        "map": tl_map,
        "seiken": seiken,
        "daijin": daijin,
    }


def rebuild_suggest(orig_suggest: list, data: list[dict]) -> list:
    # 既存カテゴリを維持（手作業の分類）。検索自体は全careerを見る。
    return orig_suggest


def load_original_suggest() -> list:
    text = SRC_HTML.read_text(encoding="utf-8")
    script = text[text.find("<script>") + 8 :]
    raw = extract_js_literal(script, "const SUGGEST_DATA", "[", "]")
    return json.loads(raw)


def load_original_entry_years() -> list:
    text = SRC_HTML.read_text(encoding="utf-8")
    script = text[text.find("<script>") + 8 :]
    raw = extract_js_literal(script, "const ENTRY_YEARS", "[", "]")
    return json.loads(raw)


def main(out_dir: Path) -> None:
    data = load_json(out_dir / "data_filled.json")
    for d in data:
        normalize_person(d)
    extracted = load_json(out_dir / "pdf_extract.json")
    match = load_json(out_dir / "match_result.json")
    files = {m["file"]: m for m in extracted["files"]}
    chosen = choose_rep_files(extracted["files"])
    dump_json(
        out_dir / "representative_pdfs.json",
        {fy: {"file": v["file"], "as_of": v["as_of"]} for fy, v in chosen.items()},
    )

    # id -> fy -> posts (from matched career rows of representative files)
    matched_by_file: dict[str, list] = defaultdict(list)
    for row in match["matched"]:
        matched_by_file[row["file"]].append(row)
    political_by_file: dict[str, list] = defaultdict(list)
    for row in match["political"]:
        political_by_file[row["file"]].append(row)

    people = {d["id"]: d for d in data}

    apply_fys = [fy for fy in ["令和５年度", "令和６年度", "令和７年度", "令和８年度", "令和４年度"] if fy in chosen]
    added = 0
    skipped_existing = 0
    for fy in apply_fys:
        meta = chosen[fy]
        rows = matched_by_file.get(meta["file"], [])
        by_pid: dict[int, list[str]] = defaultdict(list)
        for r in rows:
            by_pid[r["id"]].append(r["post_raw"])
        for pid, posts in by_pid.items():
            person = people.get(pid)
            if not person:
                continue
            already = any((c.get("年度") or "") == fy for c in person.get("career") or [])
            if already:
                skipped_existing += 1
                continue
            post = clean_post(pick_primary_post(posts))
            if not post:
                continue
            career = person.setdefault("career", [])
            career.insert(0, {"年度": fy, "ポスト": post})
            added += 1
        for person in people.values():
            rebuild_latest_fields(person)

    n_override = apply_career_overrides(people)

    # R2-R4 verification
    verify_rows = []
    for fy, _target in VERIFY_FY.items():
        if fy not in chosen:
            continue
        meta = chosen[fy]
        rows = matched_by_file.get(meta["file"], [])
        by_pid: dict[int, list[str]] = defaultdict(list)
        for r in rows:
            by_pid[r["id"]].append(r["post_raw"])
        substrs = [fy, nfkc(fy)]
        for pid, posts in by_pid.items():
            person = people.get(pid)
            if not person:
                continue
            pdf_post = pick_primary_post(posts)
            html_post = career_post_for_fy(person, substrs)
            if pdf_post != html_post:
                verify_rows.append(
                    {
                        "fy": fy,
                        "file": meta["file"],
                        "id": pid,
                        "n": person["n"],
                        "pdf_post": pdf_post,
                        "html_post": html_post,
                    }
                )

    daijin_by_fy = {}
    for fy, meta in chosen.items():
        ministers = [
            r
            for r in political_by_file.get(meta["file"], [])
            if compact_is_minister(r["post_raw"])
        ]
        if ministers:
            daijin_by_fy[fy] = compact_name(ministers[0]["name_raw"])

    orig_tl = load_original_tl()
    tl = rebuild_tl(list(people.values()), daijin_by_fy, orig_tl)
    apply_pdf_spans(tl, extracted, match, people)
    suggest = rebuild_suggest(load_original_suggest(), list(people.values()))
    entry_years = load_original_entry_years()

    out_data = list(people.values())
    out_data.sort(key=lambda d: d["id"])
    dump_json(out_dir / "DATA.json", out_data, indent=None)
    dump_json(out_dir / "TL_DATA.json", tl, indent=None)
    dump_json(out_dir / "SUGGEST_DATA.json", suggest, indent=None)
    dump_json(out_dir / "ENTRY_YEARS.json", entry_years)

    with (out_dir / "r2_r4_pdf_vs_html.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["fy", "file", "id", "n", "pdf_post", "html_post"])
        w.writeheader()
        w.writerows(verify_rows)

    # 新出（代表PDFの unmatched）
    new_names = []
    for fy in apply_fys:
        fn = chosen[fy]["file"]
        for row in match["unmatched"]:
            if row["file"] == fn:
                new_names.append({**row, "fy": fy})
    with (out_dir / "new_names_not_added.csv").open("w", encoding="utf-8-sig", newline="") as f:
        fields = ["fy", "file", "post_raw", "name_raw", "yomi_raw", "kind"]
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(new_names)

    dump_json(
        out_dir / "merge_stats.json",
        {
            "people": len(out_data),
            "career_years_added": added,
            "career_overrides": n_override,
            "skipped_existing": skipped_existing,
            "apply_fys": apply_fys,
            "r2_r4_diff": len(verify_rows),
            "new_names_not_added": len(new_names),
            "daijin_by_fy": daijin_by_fy,
            "rep": {fy: chosen[fy]["file"] for fy in sorted(chosen)},
        },
    )
    print("added", added, "overrides", n_override, "r2_r4_diff", len(verify_rows), "new_names", len(new_names))


def compact_is_minister(post: str) -> bool:
    p = (post or "").replace(" ", "").replace("　", "")
    return p in {"大臣", "財務大臣"}


def compact_name(name: str) -> str:
    return unify_display(name or "").replace(" ", "").replace("　", "")


def compact_post(post: str) -> str:
    return unify_display(post or "").replace(" ", "").replace("　", "")


CABINETS = [
    (date(2020, 9, 16), "菅義偉"),
    (date(2021, 10, 4), "岸田文雄（第1次）"),
    (date(2021, 11, 10), "岸田文雄（第2次）"),
    (date(2022, 8, 10), "岸田文雄（第2次改造）"),
    (date(2023, 9, 13), "岸田文雄（第2次改造②）"),
    (date(2024, 10, 1), "石破茂（第1次）"),
    (date(2024, 11, 11), "石破茂（第2次）"),
    (date(2025, 10, 21), "高市早苗（第1次）"),
    (date(2026, 2, 18), "高市早苗（第2次）"),
]


def cabinet_on(d: date) -> str:
    name = ""
    for start, lab in CABINETS:
        if d >= start:
            name = lab
    return name


def md(d: date) -> str:
    return f"{d.month}.{d.day}"


def compress_spans(seq: list[tuple[date, str]]) -> list[tuple[str, date, date]]:
    if not seq:
        return []
    seq = sorted(seq, key=lambda x: x[0])
    out = []
    name0, d0 = seq[0][1], seq[0][0]
    prev = d0
    for d, name in seq[1:]:
        if name == name0:
            prev = d
            continue
        out.append((name0, d0, prev))
        name0, d0, prev = name, d, d
    out.append((name0, d0, prev))
    return out


def fmt_spans(spans: list[tuple[str, date, date]]) -> str:
    if not spans:
        return ""
    if len(spans) == 1:
        return spans[0][0]
    parts = []
    for name, d0, d1 in spans:
        if d0 == d1:
            parts.append(f"{name}（{md(d0)}）")
        else:
            parts.append(f"{name}（{md(d0)}〜{md(d1)}）")
    return "\n".join(parts)


def apply_pdf_spans(tl: dict, extracted: dict, match: dict, people: dict) -> None:
    """年度内の大臣・政権・次官の交代を、PDF全件から日付付きで年表へ載せる。"""
    files = {m["file"]: m for m in extracted["files"]}
    daijin_seq = defaultdict(list)
    seiken_seq = defaultdict(list)
    jikan_seq = defaultdict(list)

    for r in match.get("political") or []:
        meta = files.get(r["file"])
        if not meta or not meta.get("as_of") or not compact_is_minister(r.get("post_raw") or ""):
            continue
        fy = meta["fy"]
        d = date.fromisoformat(meta["as_of"])
        name = compact_name(r.get("name_raw") or "")
        if name:
            daijin_seq[fy].append((d, name))
            cab = cabinet_on(d)
            if cab:
                seiken_seq[fy].append((d, cab))

    for r in match.get("matched") or []:
        meta = files.get(r["file"])
        if not meta or not meta.get("as_of"):
            continue
        if compact_post(r.get("post_raw") or "") != "事務次官":
            continue
        fy = meta["fy"]
        d = date.fromisoformat(meta["as_of"])
        person = people.get(r["id"])
        name = (person or {}).get("n") or r.get("n") or ""
        jikan_seq[fy].append((d, name, r["id"], (person or {}).get("yf") or ""))

    for fy, seq in seiken_seq.items():
        spans = compress_spans(seq)
        if spans:
            tl.setdefault("seiken", {})[fy] = fmt_spans(spans)
    for fy, seq in daijin_seq.items():
        spans = compress_spans(seq)
        if spans:
            tl.setdefault("daijin", {})[fy] = fmt_spans(spans)

    for fy, seq in jikan_seq.items():
        seq_sorted = sorted(seq, key=lambda x: x[0])
        # compress by id
        chunks = []
        cur = None
        for d, name, pid, yf in seq_sorted:
            if cur and cur["id"] == pid:
                cur["d1"] = d
                continue
            if cur:
                chunks.append(cur)
            cur = {"name": name, "id": pid, "yf": yf, "d0": d, "d1": d}
        if cur:
            chunks.append(cur)
        arr = []
        multi = len(chunks) > 1
        for ch in chunks:
            rec = {"name": ch["name"], "id": ch["id"], "yf": ch["yf"]}
            if multi:
                if ch["d0"] == ch["d1"]:
                    rec["span"] = md(ch["d0"])
                else:
                    rec["span"] = f"{md(ch['d0'])}〜{md(ch['d1'])}"
            arr.append(rec)
        if arr:
            tl.setdefault("map", {}).setdefault(fy, {})["事務次官"] = arr


def compact_is_jikan(post: str) -> bool:
    return compact_post(post) == "事務次官"


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    main(Path(args.out))
