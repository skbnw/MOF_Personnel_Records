# -*- coding: utf-8 -*-
"""既存JSONから HTML だけ再組立する。"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE_DIR))
from lib.common import OUTPUT_ROOT, now_stamp  # noqa: E402
from rebuild_html import main as rebuild_main  # noqa: E402


def main() -> None:
    src = OUTPUT_ROOT / "20260904_1351"
    out = OUTPUT_ROOT / now_stamp()
    out.mkdir(parents=True, exist_ok=True)
    for name in ("DATA.json", "TL_DATA.json", "SUGGEST_DATA.json", "ENTRY_YEARS.json"):
        shutil.copy2(src / name, out / name)
    rebuild_main(out)
    print("OUT", out)


if __name__ == "__main__":
    main()
