#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kho_3shape.py — ĐỌC KHO DỮ LIỆU 3Shape Ortho System (chỉ đọc) để chọn bệnh nhân / model set.

Cấu trúc trên đĩa (Ortho System 2021): <OrthoData>/<mã BN>/OrthoPatientInfo.xml
   + <OrthoData>/<mã BN>/<model set>/OrthoModelSetInfo.xml + Tooth_N.dcm (nếu đã segment)
Ngày tháng lưu kiểu Delphi TDateTime (số ngày kể từ 1899-12-30).
"""
import json
import re
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

GOC_MAC_DINH = Path(r"C:\ProgramData\3Shape\OrthoData")
RE_TOOTH = re.compile(r"^Tooth_(\d+)\.dcm$", re.I)
_RE_PROP = re.compile(r'<Property name="(\w+)" value="([^"]*)"/>')


def _props(path: Path) -> dict:
    try:
        return dict(_RE_PROP.findall(path.read_text(encoding="utf-8", errors="replace")))
    except Exception:
        return {}


def _ngay_delphi(s: str):
    try:
        return datetime(1899, 12, 30) + timedelta(days=float(s))
    except Exception:
        return None


def khoa_so_sanh(s: str) -> str:
    """Bỏ dấu, thường hóa, chỉ giữ chữ+số để so tên bệnh nhân với tên ca."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def do_giong(a: str, b: str) -> float:
    """0..1: tỉ lệ từ (token) chung giữa 2 chuỗi (đã chuẩn hóa); chuỗi con nguyên cũng tính."""
    ka, kb = khoa_so_sanh(a), khoa_so_sanh(b)
    if not ka or not kb:
        return 0.0
    if ka in kb or kb in ka:
        return 1.0
    ta, tb = set(ka.split()), set(kb.split())
    ta = {t for t in ta if len(t) > 1}
    tb = {t for t in tb if len(t) > 1}
    if not ta or not tb:
        return 0.0
    diem = 0.0
    for x in ta:
        best = 0.0
        for y in tb:
            if x == y:
                best = 1.0
                break
            # tiền tố chung ≥4 chữ (nguyenvana ~ nguyenvan) tính 0.6
            n = 0
            for c1, c2 in zip(x, y):
                if c1 != c2:
                    break
                n += 1
            if n >= 4:
                best = max(best, 0.6)
        diem += best
    return diem / min(len(ta), len(tb))


def schema_dcm(path: Path) -> str:
    """'CA'/'CC' (đọc được) | 'CE' (3Shape mã hóa) | '?'."""
    try:
        with open(path, "rb") as f:
            dau = f.read(400).decode("latin1")
        m = re.search(r"<Schema>(\w+)</Schema>", dau)
        return m.group(1) if m else "?"
    except Exception:
        return "?"


def doc_model_set(ms_dir: Path) -> dict:
    p = _props(ms_dir / "OrthoModelSetInfo.xml")
    files = {int(m.group(1)): f for f in ms_dir.glob("Tooth_*.dcm") if (m := RE_TOOTH.match(f.name))}
    teeth = sorted(files)
    ma_hoa = sorted(n for n, f in files.items() if schema_dcm(f) == "CE")
    # răng CE nhưng 3Shape ghi kèm Models/Tooth_N.stl cùng lúc → dựng lại được
    dung_lai = sorted(n for n in ma_hoa
                      if (ms_dir / "Models" / f"Tooth_{n}.stl").is_file()
                      and abs((ms_dir / "Models" / f"Tooth_{n}.stl").stat().st_mtime - files[n].stat().st_mtime) <= 120)
    ghep = None
    jf = ms_dir / "_chan_rang_cbct.json"
    if jf.is_file():
        try:
            ghep = json.loads(jf.read_text(encoding="utf-8"))
        except Exception:
            ghep = {"thoi_gian": "?"}
    return {
        "duong_dan": str(ms_dir),
        "ten": ms_dir.name,
        "id": p.get("wsModelSetID", ms_dir.name),
        "ghi_chu": p.get("wsModelSetComment", ""),
        "ngay": _ngay_delphi(p.get("dtModelSetDate", "")),
        "trang_thai": p.get("wsModelSetStatus", ""),
        "ham_tren": p.get("bAttachedUpper", "") == "True",
        "ham_duoi": p.get("bAttachedLower", "") == "True",
        "rang": teeth,
        "so_rang": len(teeth),
        "rang_ma_hoa": ma_hoa,          # răng 3Shape đã lưu lại dạng CE (sau khi làm mịn/lưu setup)
        "rang_dung_lai": dung_lai,      # trong số đó, răng có STL kèm → dựng lại được
        "dang_mo": (ms_dir / "lock.lck").exists(),
        "da_ghep": ghep,
    }


def doc_benh_nhan(bn_dir: Path) -> dict | None:
    f = bn_dir / "OrthoPatientInfo.xml"
    if not f.is_file():
        return None
    p = _props(f)
    ho_ten = " ".join(x for x in (p.get("wsPatientFirstName", ""), p.get("wsPatientLastName", "")) if x).strip()
    ms = []
    for d in sorted(bn_dir.iterdir()):
        if d.is_dir() and (d / "OrthoModelSetInfo.xml").is_file():
            ms.append(doc_model_set(d))
    ms.sort(key=lambda m: (m["ngay"] or datetime.min), reverse=True)
    return {
        "duong_dan": str(bn_dir),
        "id": p.get("wsPatientID", bn_dir.name),
        "ho_ten": ho_ten or "(không tên)",
        "ma_ngoai": p.get("wsPatientExternalID", ""),
        "model_sets": ms,
    }


def quet_kho(goc: Path = GOC_MAC_DINH) -> list[dict]:
    goc = Path(goc)
    if not goc.is_dir():
        return []
    kq = []
    for d in sorted(goc.iterdir()):
        if d.is_dir():
            bn = doc_benh_nhan(d)
            if bn:
                kq.append(bn)
    return kq


def goi_y(benh_nhan: list[dict], ten_ca: str, ten_thu_muc_dicom: str = "") -> list[tuple[float, dict]]:
    """Xếp bệnh nhân theo độ giống với tên ca / thư mục DICOM (giảm dần), chỉ trả về > 0."""
    ra = []
    for bn in benh_nhan:
        chuoi_bn = f"{bn['ho_ten']} {bn['id']} {bn['ma_ngoai']}"
        s = max(do_giong(chuoi_bn, ten_ca), do_giong(chuoi_bn, ten_thu_muc_dicom))
        if s > 0:
            ra.append((s, bn))
    ra.sort(key=lambda x: -x[0])
    return ra


def mo_ta_ngay(d):
    return d.strftime("%d/%m/%Y %H:%M") if d else "?"
