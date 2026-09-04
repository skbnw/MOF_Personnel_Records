# -*- coding: utf-8 -*-
"""
v1.1 共通ユーティリティ
- 追加: 氏名・学歴・ポストの文字幅統一（半角カナ→全角、全角英数→半角）
- 追加: ROOT を code/lib からの相対パスに変更（公開HTMLはプロジェクト直下 index.html）
- 継承: 既存HTMLの DATA スキーマ（id,n,y,r,u,h,p,fy,cnt,career,yf）
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PDF_DIR = ROOT / "original_pdf"
XLSX_DIR = ROOT / "original_xlsx"
SRC_HTML = ROOT / "index.html"
OUTPUT_ROOT = ROOT / "output"

XLSX_2022 = XLSX_DIR / "2022財務省「裏表紙」（パスワードなし）.xlsx"
XLSX_2020 = XLSX_DIR / "2020財務省「裏表紙」(令和２年度人事更新) .xlsx"
XLSX_2016 = XLSX_DIR / "2016財務省官僚人事一覧「裏表紙」.xlsx"

POLITICAL_EXACT = {"大臣", "副大臣", "大臣政務官"}
POLITICAL_PREFIX = ("副大臣", "大臣政務官")

# PDF常用漢字 ↔ 裏表紙の旧字ゆれ
KANJI_MAP = str.maketrans(
    {
        "髙": "高",
        "﨑": "崎",
        "邉": "辺",
        "邊": "辺",
        "德": "徳",
        "眞": "真",
        "澤": "沢",
        "廣": "広",
        "濵": "浜",
        "濱": "浜",
        "齋": "斎",
        "斉": "斎",
        "榮": "栄",
        "實": "実",
        "國": "国",
        "滿": "満",
        "瀨": "瀬",
        "諸": "諸",
        "栁": "柳",
    }
)

ERA_WESTERN = {
    "明治": ("M", 1868),
    "明": ("M", 1868),
    "大正": ("T", 1912),
    "大": ("T", 1912),
    "昭和": ("S", 1926),
    "昭": ("S", 1926),
    "平成": ("H", 1989),
    "平": ("H", 1989),
    "令和": ("R", 2019),
    "令": ("R", 2019),
}


def nfkc(s: str) -> str:
    return unicodedata.normalize("NFKC", s or "")


def unify_display(s: str) -> str:
    """半角カナ→全角カナ、全角英数→半角英数。"""
    return unicodedata.normalize("NFKC", s or "")


def clean_name(s: str) -> str:
    s = unify_display(s).replace("\u3000", " ")
    return re.sub(r" {2,}", " ", s).strip()


def clean_post(s: str) -> str:
    """ポスト表記の幅・空白・中黒・兼/矢印まわりを揃える。年度ラベルは触らない。"""
    s = unify_display(s)
    s = s.replace("\u3000", " ")
    s = s.replace("･", "・").replace("．", ".")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"(?<=\S)\s*←\s*(?=\S)", " ← ", s)
    s = re.sub(r"(?<=\S)\s*→\s*(?=\S)", " → ", s)
    s = re.sub(r"(?<=\S)\s*兼\s*(?=\S)", " 兼 ", s)
    return s.strip()


def normalize_person(d: dict) -> dict:
    d["n"] = clean_name(d.get("n") or "")
    d["r"] = unify_display(d.get("r") or "").replace(" ", "").replace("\u3000", "")
    d["u"] = unify_display(d.get("u") or "").strip()
    d["h"] = unify_display(d.get("h") or "").strip()
    d["p"] = clean_post(d.get("p") or "")
    for c in d.get("career") or []:
        c["ポスト"] = clean_post(c.get("ポスト") or "")
    return d


def compact_text(s: str) -> str:
    s = nfkc(str(s or ""))
    s = s.replace("\n", "").replace("\r", "")
    s = re.sub(r"\s+", "", s)
    return s


def canon_kanji(s: str) -> str:
    return compact_text(s).translate(KANJI_MAP)


def canon_yomi(s: str) -> str:
    s = compact_text(s).replace("　", "")
    s = s.replace("ー", "").replace("−", "").replace("-", "")
    return s


def display_name_from_spaced(s: str) -> str:
    """PDFの一字空き氏名を『姓 名』に近づける。空白を全部除去して返すだけでも照合は可能。"""
    s = nfkc(s or "").strip()
    s = re.sub(r"\s+", "", s)
    return s


def is_political_post(post: str) -> bool:
    p = compact_text(post)
    if not p:
        return False
    if p in POLITICAL_EXACT:
        return True
    if p.startswith("大臣政務官") or p.startswith("副大臣"):
        return True
    # 『大臣』単体のみ。大臣官房長・財務大臣秘書官はキャリア
    if p == "大臣" or p == "財務大臣":
        return True
    return False


def parse_filename_date(name: str) -> date | None:
    m = re.search(r"meiboR(\d{2})(\d{2})(\d{2})", name, re.I)
    if not m:
        return None
    ry, mo, dy = int(m.group(1)), int(m.group(2)), int(m.group(3))
    western = 2018 + ry  # 令和1=2019 → 01 → 2019 = 2018+1
    return date(western, mo, dy)


def parse_text_date(text: str) -> date | None:
    t = nfkc(text)
    m = re.search(r"令和\s*(\d+|元)\s*年\s*(\d+)\s*月\s*(\d+)\s*日", t)
    if not m:
        return None
    ry = 1 if m.group(1) == "元" else int(m.group(1))
    return date(2018 + ry, int(m.group(2)), int(m.group(3)))


def fy_label_from_date(d: date) -> str:
    """西暦日付 → 『令和Ｎ年度』（数字は全角、令和4以降のDATA表記に合わせる）"""
    if d.month >= 4:
        reiwa = d.year - 2018
    else:
        reiwa = d.year - 2019
    return f"令和{to_zen_num(reiwa)}年度"


def to_zen_num(n: int) -> str:
    tbl = str.maketrans("0123456789", "０１２３４５６７８９")
    return str(n).translate(tbl)


def fy_fmt(raw: str) -> str:
    """『令和４年度』→ 2022_R04。既存TL_DATAのfmt規則に合わせる。"""
    s = nfkc(raw)
    s = s.replace("年度", "")
    # 平成31年度(令和元年度) 等
    if "令和元" in raw or ( "平成31" in nfkc(raw) and "令和" in raw):
        return "2019_R01"
    m = re.search(r"(明治|大正|昭和|平成|令和|明|大|昭|平|令)元", s)
    if m:
        letter, start = ERA_WESTERN[m.group(1)]
        return f"{start}_{letter}01"
    m = re.search(r"(明治|大正|昭和|平成|令和|明|大|昭|平|令)\s*(\d+)", s)
    if not m:
        return ""
    letter, start = ERA_WESTERN[m.group(1)]
    n = int(m.group(2))
    western = start + n - 1
    return f"{western}_{letter}{n:02d}"


def fy_sort_key(raw: str) -> tuple:
    fmt = fy_fmt(raw)
    m = re.match(r"(\d{4})_([A-Z])(\d+)", fmt)
    if not m:
        return (9999, 99)
    return (int(m.group(1)), int(m.group(3)))


def extract_js_literal(script: str, decl: str, opener: str, closer: str) -> str:
    i = script.find(decl)
    if i < 0:
        raise ValueError(f"declaration not found: {decl}")
    start = script.find(opener, i)
    depth = 0
    in_str = False
    esc = False
    quote = ""
    for k, ch in enumerate(script[start:], start):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == quote:
                in_str = False
            continue
        if ch in "\"'":
            in_str = True
            quote = ch
            continue
        if ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return script[start : k + 1]
    raise ValueError(f"unclosed literal for {decl}")


def load_html_data(html_path: Path | None = None) -> tuple[list, str]:
    path = html_path or SRC_HTML
    text = path.read_text(encoding="utf-8")
    si = text.find("<script>")
    script = text[si + 8 :]
    raw = extract_js_literal(script, "const DATA = ", "[", "]")
    data = json.loads(raw)
    return data, text


def dump_json(path: Path, obj, indent: int | None = 2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, ensure_ascii=False, indent=indent),
        encoding="utf-8",
    )


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M")
