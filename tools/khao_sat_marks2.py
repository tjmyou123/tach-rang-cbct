# -*- coding: utf-8 -*-
"""Kiểm chứng ý nghĩa FacetMarks: nhóm nào trùng bề mặt scan (thân răng), nhóm nào là chân ảo."""
import sys
from pathlib import Path
import numpy as np
from hpsdecode import load_hps
from scipy.spatial import cKDTree
import vtk
from vtk.util.numpy_support import vtk_to_numpy

D = Path(r"e:\dental segment\data_test\3shape_khao_sat")
name = sys.argv[1] if len(sys.argv) > 1 else "Tooth_8"
SCAN = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(r"e:\dental segment\CBCT_input\HO THI THU HUONG\scan\9172022-bs huong 07-maxillary.stl")
r = vtk.vtkSTLReader(); r.SetFileName(str(SCAN)); r.Update()
Vs = vtk_to_numpy(r.GetOutput().GetPoints().GetData()).astype(np.float64)
cay = cKDTree(Vs)
pk, m = load_hps(str(D / f"{name}.dcm"))
V, F = m.vertices.astype(np.float64), m.faces
marks = np.load(D / f"{name}_marks.npy")
C = V[F].mean(axis=1)
d, _ = cay.query(C)
hi = marks >> 24
for h in np.unique(hi):
    sel = hi == h
    print(f"byte cao {h:#04x}: n={sel.sum():5d} | cách scan: median {np.median(d[sel]):.3f} p90 {np.percentile(d[sel],90):.3f} | tỉ lệ <0.05mm: {(d[sel]<0.05).mean()*100:5.1f}%")
lo = marks & 0xFFFF
for l in np.unique(lo):
    sel = lo == l
    print(f"  16 bit thấp {l:#06x}: n={sel.sum():5d} | cách scan median {np.median(d[sel]):.3f} | y tb {C[sel,1].mean():.2f}")
# đỉnh: những đỉnh chỉ thuộc facet 0x08 => chân ảo
