# -*- coding: utf-8 -*-
"""cau_hinh.py — Mọi đường dẫn của chương trình ở MỘT chỗ, không đường dẫn cứng.

Thứ tự ưu tiên cho từng thư mục:
  1. biến môi trường  (TACHRANG_MODELS, TACHRANG_INPUT, TACHRANG_OUTPUT, TACHRANG_LOGS)
  2. file config.json cạnh thư mục gốc dự án (portable — copy cả thư mục sang máy khác vẫn chạy)
  3. mặc định: <gốc dự án>/models, CBCT_input, ket_qua, logs

Gốc dự án = thư mục chứa package `tachrang` (hoặc thư mục chứa file .exe khi đóng gói).
"""

import json
import os
import sys
from pathlib import Path

_KHOA = ("models_dir", "input_dir", "output_dir", "logs_dir")
_ENV = {"models_dir": "TACHRANG_MODELS", "input_dir": "TACHRANG_INPUT",
        "output_dir": "TACHRANG_OUTPUT", "logs_dir": "TACHRANG_LOGS"}
_MAC_DINH = {"models_dir": "models", "input_dir": "CBCT_input",
             "output_dir": "ket_qua", "logs_dir": "logs"}


def goc_du_an() -> Path:
    """Thư mục gốc: nơi đặt models/, config.json, logs/ ..."""
    if getattr(sys, "frozen", False):          # PyInstaller
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def duong_config() -> Path:
    return goc_du_an() / "config.json"


def doc_cau_hinh() -> dict:
    """Trả về dict đủ 4 khóa, giá trị là Path tuyệt đối."""
    goc = goc_du_an()
    cfg = {}
    p = duong_config()
    if p.is_file():
        try:
            cfg = json.loads(p.read_text(encoding="utf-8")) or {}
        except (OSError, ValueError):
            cfg = {}
    ket = {}
    for k in _KHOA:
        v = os.environ.get(_ENV[k]) or cfg.get(k) or _MAC_DINH[k]
        v = Path(str(v)).expanduser()
        ket[k] = v if v.is_absolute() else (goc / v)
    return ket


def ghi_cau_hinh(**thay_doi) -> Path:
    """Cập nhật một vài khóa vào config.json (giữ các khóa khác)."""
    p = duong_config()
    cfg = {}
    if p.is_file():
        try:
            cfg = json.loads(p.read_text(encoding="utf-8")) or {}
        except (OSError, ValueError):
            cfg = {}
    for k, v in thay_doi.items():
        if k in _KHOA and v is not None:
            cfg[k] = str(v)
    p.write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def thu_muc_models(ten: str = "") -> Path:
    d = doc_cau_hinh()["models_dir"]
    return d / ten if ten else d


def thu_muc_input() -> Path:
    return doc_cau_hinh()["input_dir"]


def thu_muc_output() -> Path:
    return doc_cau_hinh()["output_dir"]


def thu_muc_logs() -> Path:
    d = doc_cau_hinh()["logs_dir"]
    d.mkdir(parents=True, exist_ok=True)
    return d


def python_chay() -> str:
    """Trình python để chạy tiến trình con (pipeline). Khi đóng gói exe thì
    chính là exe này (xử lý ở __main__)."""
    return sys.executable
