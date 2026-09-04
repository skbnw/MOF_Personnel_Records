# -*- coding: utf-8 -*-
"""
v1.0 セットアップ補助
- venv / code / output フォルダ確認
- 依存パッケージ一覧の出力
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for name in ["code", "output", "venv"]:
    (ROOT / name).mkdir(exist_ok=True)
print("ROOT", ROOT)
print("folders ok")
