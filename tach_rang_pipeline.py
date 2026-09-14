#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lịch tương thích: mã thật nằm ở tachrang/core/pipeline.py.
    python tach_rang_pipeline.py -i ... -o ...   ==   python -m tachrang.core.pipeline ...
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tachrang.core.pipeline import *   # noqa: E402,F401,F403 — giữ API cũ (pl.xxx)
from tachrang.core.pipeline import main  # noqa: E402

if __name__ == "__main__":
    main()
