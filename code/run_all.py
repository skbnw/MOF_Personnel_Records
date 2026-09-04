# -*- coding: utf-8 -*-
"""
v1.0 全ステップ実行
- 追加: 01抽出 → 02 PDF → 03照合 → 04マージ → 05 HTML再組立
- 出力: output/yyyymmdd_HHmm/
"""
from __future__ import annotations

import sys
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CODE_DIR))

from lib.common import OUTPUT_ROOT, now_stamp  # noqa: E402


def main() -> Path:
    out_dir = OUTPUT_ROOT / now_stamp()
    out_dir.mkdir(parents=True, exist_ok=True)
    print("OUT", out_dir)

    from importlib import import_module

    sys.path.insert(0, str(CODE_DIR / "01-xlsx-parse"))
    sys.path.insert(0, str(CODE_DIR / "02-pdf-extract"))
    sys.path.insert(0, str(CODE_DIR / "03-name-match"))
    sys.path.insert(0, str(CODE_DIR / "04-merge-update"))
    sys.path.insert(0, str(CODE_DIR / "05-rebuild-html"))

    import_module("extract_base").main(out_dir)
    import_module("extract_pdfs").main(out_dir)
    import_module("match_names").main(out_dir)
    import_module("merge_update").main(out_dir)
    import_module("rebuild_html").main(out_dir)
    print("DONE", out_dir)
    return out_dir


if __name__ == "__main__":
    main()
