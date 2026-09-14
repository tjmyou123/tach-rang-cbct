# -*- coding: utf-8 -*-
"""Đo sai số thân răng hàm lai so với scan gốc (đỉnh răng gần scan < 1 mm)."""
import json, sys
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
GOC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GOC))
from tachrang.core.ham_lai import _doc_polydata, _pd_sang_numpy, _phap_tuyen_dinh

case = sys.argv[1]; ham = sys.argv[2]
d = GOC / "ket_qua" / "stl" / case / "ham-lai"
kq = json.loads((d / f"{case}_Ham-{ham}_lai-3shape.json").read_text(encoding="utf-8"))
Vs, Fs = _pd_sang_numpy(_doc_polydata(kq["scan"]))
Ns = _phap_tuyen_dinh(Vs, Fs); cay = cKDTree(Vs)
Vl, Fl = _pd_sang_numpy(_doc_polydata(kq["file"]))
# đỉnh hàm lai KHÔNG thuộc scan (tức là răng): cách scan gốc > 1e-6 hoặc thuộc răng — lấy đơn giản: mọi đỉnh
dist, idx = cay.query(Vl, k=1)
h = np.abs(np.einsum("ij,ij->i", Vl - Vs[idx], Ns[idx]))
gan = dist < 1.0
print(f"đỉnh hàm lai gần scan <1mm: {gan.sum()} ; |h| median {np.median(h[gan]):.3f} mm, "
      f"p90 {np.percentile(h[gan], 90):.3f}, p99 {np.percentile(h[gan], 99):.3f}, "
      f"tỉ lệ |h|<0.05: {(h[gan] < 0.05).mean() * 100:.1f}%")
