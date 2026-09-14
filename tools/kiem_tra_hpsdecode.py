# -*- coding: utf-8 -*-
"""hpsdecode giải mã Tooth_8.dcm gốc có ĐÚNG lưới như Models/Tooth_8.stl (do 3Shape ghi) không?
So tập tam giác theo tọa độ (bất biến thứ tự)."""
import sys
from pathlib import Path
import numpy as np
import vtk
from vtk.util.numpy_support import vtk_to_numpy
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tachrang.core.chan_rang_3shape import doc_dcm

D = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"e:\dental segment\backup_3shape\1222_20260908_163527\1")
ten = sys.argv[2] if len(sys.argv) > 2 else "Tooth_8"


def tap(V, F):
    P = np.round(V[F], 4)
    out = set()
    for tri in P:
        a, b, c = map(tuple, tri)
        out.add(min((a, b, c), (b, c, a), (c, a, b)))
    return out


def tap_khong_chieu(V, F):
    P = np.round(V[F], 4)
    return {tuple(sorted(map(tuple, tri))) for tri in P}


d = doc_dcm(D / f"{ten}.dcm")
r = vtk.vtkSTLReader(); r.SetFileName(str(D / "Models" / f"{ten}.stl")); r.Update()
pd = r.GetOutput()
Vs = vtk_to_numpy(pd.GetPoints().GetData()).astype(np.float64)
Fs = vtk_to_numpy(pd.GetPolys().GetData()).reshape(-1, 4)[:, 1:]
A, B = tap(d["V"], d["F"]), tap(Vs, Fs)
A2, B2 = tap_khong_chieu(d["V"], d["F"]), tap_khong_chieu(Vs, Fs)
print(f"{ten}: DCM {len(d['F'])} facet, STL {len(Fs)} facet")
print(f"  cùng chiều: chung {len(A & B)}, chỉ DCM {len(A - B)}, chỉ STL {len(B - A)}")
print(f"  bỏ chiều : chung {len(A2 & B2)}, chỉ DCM {len(A2 - B2)}, chỉ STL {len(B2 - A2)}")
# facet nào của DCM sai? in vài ví dụ vị trí trong stream
sai = [i for i, tri in enumerate(np.round(d["V"][d["F"]], 4)) if min(tuple(map(tuple, tri)), tuple(map(tuple, tri[[1, 2, 0]])), tuple(map(tuple, tri[[2, 0, 1]]))) not in B]
print("  chỉ số facet DCM không có trong STL (đầu):", sai[:20], "... tổng", len(sai))
