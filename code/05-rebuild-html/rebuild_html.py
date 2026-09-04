# -*- coding: utf-8 -*-
"""
v1.5 260513 の UI に更新データを差し込み
- 追加: DATA / ENTRY_YEARS / TL_DATA / SUGGEST_DATA の差し替え
- 追加: 名簿の在職中フィルタ、検索結果CSV出力
- 追加: 役職年表の初期表示を最新年度（2026）起点、交代者は新しい順
- 追加: 経歴一覧などの年度表示を 2025_R07年度 形式に統一
- 追加: 出力フォルダへ名簿・経歴・年表 CSV を書き出し、公開用 index.html をプロジェクト直下へコピー
- 継承: CSS・4タブUI・RANK_DEF・検索/詳細/年表のJS関数は原則維持
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE_DIR))
from lib.common import SRC_HTML, extract_js_literal, fy_fmt, unify_display  # noqa: E402

COMMENT_OLD = "v1.1 財務官僚名簿データベース"
COMMENT_NEW = """<!--
v1.5 財務官僚名簿データベース
継承: 260513_MOFPersonnel Records / GitHub skbnw/MOF_Personnel_Records
追加: 幹部名簿PDFによる令和5-8年度ポスト追記（代表日=各年度8月1日最近傍、令和8=2026-08-07）
追加: 文字幅統一（半角カナ→全角）、ポスト表記のクレンジング、年度内の大臣・次官交代を日付付き表示
追加: 役職年表は最新年度を起点、同一セルは新しい在任者を上に表示
追加: 経歴一覧などの年度表示を 2025_R07年度 形式に統一
追加: 出力CSV（名簿・経歴・年表）
照合: 2022/2020/2016裏表紙xlsx
-->
"""


def replace_literal(html: str, decl: str, opener: str, closer: str, new_literal: str) -> str:
    i = html.find(decl)
    if i < 0:
        raise ValueError(decl)
    old = extract_js_literal(html[i:], decl, opener, closer)
    start_in_slice = html[i:].find(old)
    abs_start = i + start_in_slice
    return html[:abs_start] + new_literal + html[abs_start + len(old) :]


def dumps_compact(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def ensure_roster_extras(html: str) -> str:
    if 'id="f-active"' not in html:
        html = html.replace(
            '    <button class="btn" onclick="clearRoster()">クリア</button>',
            '    <label style="display:flex;align-items:center;gap:6px;color:var(--dim);font-size:12px;white-space:nowrap;cursor:pointer">'
            '<input type="checkbox" id="f-active">在職中（令和8年度）</label>\n'
            '    <button class="btn" onclick="exportRosterCsv()">CSV</button>\n'
            '    <button class="btn" onclick="clearRoster()">クリア</button>',
            1,
        )
    if "function isActivePerson" not in html:
        html = html.replace(
            "    if(q&&!(d.n+d.r).toLowerCase().includes(q)) return false;\n    return true;",
            "    if(q&&!(d.n+d.r).toLowerCase().includes(q)) return false;\n"
            "    if(document.getElementById('f-active')&&document.getElementById('f-active').checked&&!isActivePerson(d)) return false;\n"
            "    return true;",
            1,
        )
        html = html.replace(
            "function searchRoster(){",
            "function isActivePerson(d){\n"
            "  return (d.career||[]).some(c=>/令和[8８]年度/.test(c['年度']||''));\n"
            "}\n"
            "function searchRoster(){",
            1,
        )
    if "function exportRosterCsv" not in html:
        html = html.replace(
            "function clearRoster(){",
            "function exportRosterCsv(){\n"
            "  const q=document.getElementById('s-name').value.trim().toLowerCase();\n"
            "  const era=document.getElementById('f-era').value;\n"
            "  const univ=document.getElementById('f-univ').value;\n"
            "  const active=document.getElementById('f-active')&&document.getElementById('f-active').checked;\n"
            "  const rows=DATA.filter(d=>{\n"
            "    if(era&&d.y!==era) return false;\n"
            "    if(univ&&d.u!==univ) return false;\n"
            "    if(q&&!(d.n+d.r).toLowerCase().includes(q)) return false;\n"
            "    if(active&&!isActivePerson(d)) return false;\n"
            "    return true;\n"
            "  });\n"
            "  const header=['id','氏名','読み','入省年次','入省コード','大学','高校','最新ポスト','年度','経歴数'];\n"
            "  const lines=[header.join(',')];\n"
            "  const escCsv=v=>('\"'+String(v??'').replace(/\"/g,'\"\"')+'\"');\n"
            "  rows.forEach(d=>lines.push([d.id,d.n,d.r,d.y,d.yf,d.u,d.h,d.p,d.fy,d.cnt].map(escCsv).join(',')));\n"
            "  const blob=new Blob(['\\ufeff'+lines.join('\\n')],{type:'text/csv;charset=utf-8'});\n"
            "  const a=document.createElement('a');\n"
            "  a.href=URL.createObjectURL(blob);\n"
            "  a.download='mof_personnel.csv';\n"
            "  a.click();\n"
            "  URL.revokeObjectURL(a.href);\n"
            "}\n"
            "function clearRoster(){",
            1,
        )
    if "f-active" not in html.split("function clearRoster()")[1][:400]:
        html = html.replace(
            "  document.getElementById('f-univ').value='';\n  searchRoster();",
            "  document.getElementById('f-univ').value='';\n"
            "  const act=document.getElementById('f-active');\n"
            "  if(act) act.checked=false;\n"
            "  searchRoster();",
            1,
        )
    if "'f-active'" not in html.split("['s-name','f-era','f-univ','f-sort']")[0][-80:] + html[html.find("['s-name','f-era','f-univ','f-sort']"):html.find("['s-name','f-era','f-univ','f-sort']")+80]:
        html = html.replace(
            "['s-name','f-era','f-univ','f-sort'].forEach(id=>{",
            "['s-name','f-era','f-univ','f-sort','f-active'].forEach(id=>{",
            1,
        )
    return html


def _replace_once(html: str, old: str, new: str) -> str:
    if old in html:
        return html.replace(old, new, 1)
    return html


def ensure_timeline_spans(html: str) -> str:
    html = _replace_once(
        html,
        "  const defFrom=TL_YEARS[Math.min(29,TL_YEARS.length-1)];\n"
        "  if(defFrom) fromEl.value=defFrom.raw;",
        "  const defFrom=TL_YEARS[0];\n"
        "  const defTo=TL_YEARS[Math.min(29,TL_YEARS.length-1)];\n"
        "  if(defFrom) fromEl.value=defFrom.raw;\n"
        "  if(defTo) toEl.value=defTo.raw;",
    )
    html = _replace_once(
        html,
        "        const persons=row[role]||[];",
        "        const persons=(row[role]||[]).slice().reverse();",
    )
    if "function fmtTlCell(" not in html:
        html = _replace_once(
            html,
            "function renderTimeline(){",
            "function fmtTlCell(s){\n"
            "  if(!s) return '';\n"
            "  return String(s).split(/\\n|→/).map(x=>x.trim()).filter(Boolean).reverse().map(esc).join('<br>');\n"
            "}\n"
            "function renderTimeline(){",
        )
    for old, new in (
        (
            "esc(TL_SEIKEN[y.raw]||'').split('\\n').filter(Boolean).reverse().join('<br>')",
            "fmtTlCell(TL_SEIKEN[y.raw]||'')",
        ),
        (
            "esc(TL_DAIJIN[y.raw]||'').split('\\n').filter(Boolean).reverse().join('<br>')",
            "fmtTlCell(TL_DAIJIN[y.raw]||'')",
        ),
        (
            "esc(TL_SEIKEN[y.raw]||'').replace(/\\n/g,'<br>')",
            "fmtTlCell(TL_SEIKEN[y.raw]||'')",
        ),
        (
            "esc(TL_DAIJIN[y.raw]||'').replace(/\\n/g,'<br>')",
            "fmtTlCell(TL_DAIJIN[y.raw]||'')",
        ),
    ):
        html = _replace_once(html, old, new)
    old = (
        "persons.map(p=>'<span class=\"tl-person\" onclick=\"showDetFromTimeline('+p.id+')\">'"
        "+esc(p.name)+'<span class=\"tp-entry\">'+esc(p.yf)+'</span></span>').join('<br>')"
    )
    new = (
        "persons.map(p=>'<span class=\"tl-person\" onclick=\"showDetFromTimeline('+p.id+')\">'"
        "+esc(p.name)+'<span class=\"tp-entry\">'+esc(p.yf)+(p.span?' '+esc(p.span):'')"
        "+'</span></span>').join('<br>')"
    )
    html = _replace_once(html, old, new)
    return html


def ensure_fy_display(html: str) -> str:
    html = _replace_once(
        html,
        ".ci-yr{color:var(--muted);font-size:11px;min-width:86px;",
        ".ci-yr{color:var(--muted);font-size:11px;min-width:108px;",
    )
    if "function fmtFy(" not in html:
        html = _replace_once(
            html,
            "function fmtTlCell(s){",
            "function fmtFy(raw){\n"
            "  if(!raw) return '';\n"
            "  const y=(TL_YEARS||[]).find(x=>x.raw===raw);\n"
            "  return y&&y.fmt ? y.fmt+'年度' : raw;\n"
            "}\n"
            "function fmtTlCell(s){",
        )
    html = _replace_once(
        html,
        "esc(c['年度'])",
        "esc(fmtFy(c['年度']))",
    )
    html = _replace_once(
        html,
        "'<td class=\"c-fy\">'+esc(d.fy)+'</td>'",
        "'<td class=\"c-fy\">'+esc(fmtFy(d.fy))+'</td>'",
    )
    html = _replace_once(
        html,
        "'<td class=\"pt-yr\">'+esc(year)+'</td>'",
        "'<td class=\"pt-yr\">'+esc(fmtFy(year))+'</td>'",
    )
    html = _replace_once(
        html,
        "'<span class=\"pc-year\">'+esc(bestYear)+'</span>'",
        "'<span class=\"pc-year\">'+esc(fmtFy(bestYear))+'</span>'",
    )
    return html


def unify_embedded_univ_order(html: str) -> str:
    decl = "const UNIV_ORDER="
    i = html.find(decl)
    if i < 0:
        decl = "const UNIV_ORDER ="
        i = html.find(decl)
    if i < 0:
        return html
    raw = extract_js_literal(html[i:], decl, "[", "]")
    arr = json.loads(raw)
    arr = [unify_display(x) for x in arr]
    start = i + html[i:].find(raw)
    return html[:start] + dumps_compact(arr) + html[start + len(raw) :]


def _csv_write(path: Path, header: list[str], rows: list[list]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def _join_persons(persons: list) -> str:
    parts = []
    for p in persons or []:
        name = (p.get("name") or "").replace("　", " ").strip()
        yf = p.get("yf") or ""
        span = p.get("span") or ""
        bits = [name]
        if yf:
            bits.append(yf)
        if span:
            bits.append(span)
        parts.append(" ".join(bits))
    return " / ".join(parts)


def write_output_csvs(out_dir: Path, data: list, tl: dict) -> None:
    people_rows = []
    career_rows = []
    for d in data:
        fy = d.get("fy") or ""
        people_rows.append(
            [
                d.get("id"),
                d.get("n") or "",
                d.get("r") or "",
                d.get("y") or "",
                d.get("yf") or "",
                d.get("u") or "",
                d.get("h") or "",
                d.get("p") or "",
                fy,
                fy_fmt(fy),
                d.get("cnt") or 0,
            ]
        )
        for c in d.get("career") or []:
            year = c.get("年度") or ""
            career_rows.append(
                [
                    d.get("id"),
                    d.get("n") or "",
                    d.get("yf") or "",
                    year,
                    fy_fmt(year),
                    c.get("ポスト") or "",
                ]
            )

    _csv_write(
        out_dir / "mof_personnel.csv",
        ["id", "氏名", "読み", "入省年次", "入省コード", "大学", "高校", "最新ポスト", "年度", "年度コード", "経歴数"],
        people_rows,
    )
    _csv_write(
        out_dir / "mof_career.csv",
        ["id", "氏名", "入省コード", "年度", "年度コード", "ポスト"],
        career_rows,
    )

    roles = list(tl.get("roles") or [])
    seiken = tl.get("seiken") or {}
    daijin = tl.get("daijin") or {}
    mp = tl.get("map") or {}
    tl_header = ["年度", "年度コード"] + roles
    tl_rows = []
    for y in tl.get("years") or []:
        raw = y.get("raw") or ""
        row = [raw, y.get("fmt") or fy_fmt(raw)]
        for role in roles:
            if role == "政権":
                row.append((seiken.get(raw) or "").replace("\n", " / "))
            elif role == "財務大臣":
                row.append((daijin.get(raw) or "").replace("\n", " / "))
            else:
                row.append(_join_persons((mp.get(raw) or {}).get(role) or []))
        tl_rows.append(row)
    _csv_write(out_dir / "mof_timeline.csv", tl_header, tl_rows)
    print(
        "csv",
        out_dir / "mof_personnel.csv",
        len(people_rows),
        "career",
        len(career_rows),
        "timeline",
        len(tl_rows),
    )


def main(out_dir: Path) -> None:
    data = json.loads((out_dir / "DATA.json").read_text(encoding="utf-8"))
    tl = json.loads((out_dir / "TL_DATA.json").read_text(encoding="utf-8"))
    suggest = json.loads((out_dir / "SUGGEST_DATA.json").read_text(encoding="utf-8"))
    entry = json.loads((out_dir / "ENTRY_YEARS.json").read_text(encoding="utf-8"))

    html = SRC_HTML.read_text(encoding="utf-8")
    if "v1.5 財務官僚名簿データベース" not in html:
        html = html.replace(
            html[html.find("<!--") : html.find("-->") + 3],
            COMMENT_NEW.strip(),
            1,
        )

    html = ensure_roster_extras(html)
    html = ensure_timeline_spans(html)
    html = ensure_fy_display(html)
    html = unify_embedded_univ_order(html)
    suggest = [
        {"cat": x.get("cat") or "", "items": [unify_display(i) for i in (x.get("items") or [])]}
        for x in suggest
    ]
    html = replace_literal(html, "const DATA = ", "[", "]", dumps_compact(data))
    html = replace_literal(html, "const ENTRY_YEARS = ", "[", "]", dumps_compact(entry))
    html = replace_literal(html, "const TL_DATA", "{", "}", dumps_compact(tl))
    html = replace_literal(html, "const SUGGEST_DATA = ", "[", "]", dumps_compact(suggest))

    out_path = out_dir / "index.html"
    out_path.write_text(html, encoding="utf-8")
    SRC_HTML.write_text(html, encoding="utf-8")
    write_output_csvs(out_dir, data, tl)
    print("wrote", out_path, "bytes", out_path.stat().st_size, "people", len(data))
    print("published", SRC_HTML)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    main(Path(args.out))
