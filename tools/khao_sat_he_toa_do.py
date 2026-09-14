# -*- coding: utf-8 -*-
"""So hệ tọa độ các .dcm của 3Shape (Maxillary_orig / Maxillary / Tooth_UpperJaw) với scan STL gốc."""
import re, sys
from pathlib import Path
import numpy as np
from hpsdecode import load_hps
from scipy.spatial import cKDTree
import vtk
from vtk.util.numpy_support import vtk_to_numpy

D = Path(r"e:\dental segment\data_test\3shape_khao_sat")
SCAN = Path(r"e:\dental segment\CBCT_input\HO THI THU HUONG\scan\9172022-bs huong 07-maxillary.stl")


def stl(p):
    r = vtk.vtkSTLReader(); r.SetFileName(str(p)); r.Update(); pd = r.GetOutput()
    return vtk_to_numpy(pd.GetPoints().GetData()).astype(np.float64), pd.GetNumberOfCells()


Vs, nc = stl(SCAN)
print("scan STL", Vs.shape, nc, "bbox", Vs.min(0).round(2), Vs.max(0).round(2))
cay = cKDTree(Vs)
for n in ["Maxillary_orig", "Maxillary", "Tooth_UpperJaw"]:
    p = D / f"{n}.dcm"
    if not p.exists():
        continue
    pk, m = load_hps(str(p))
    V = m.vertices.astype(np.float64)
    print(f"\n{n}: schema {pk.schema} V {V.shape} F {m.faces.shape} bbox {V.min(0).round(2)} {V.max(0).round(2)}")
    s = p.read_bytes().decode("latin1")
    print("   props:", re.findall(r'name="(OrthoModelType|Upper|ShaderMaterial|ModelType)" value="([^"]*)"', s)[:6])
    mm = re.search(r'<Matrix4x4 name="mTransferMatrix"([^/]*)/>', s)
    if mm:
        vals = dict(re.findall(r'(m\d\d)="([^"]*)"', mm.group(1)))
        M = np.array([[float(vals[f"m{i}{j}"]) for j in range(4)] for i in range(4)])
        print("   mTransferMatrix:\n", M.round(4))
    d, _ = cay.query(V)
    print(f"   -> scan STL: median {np.median(d):.4f} p90 {np.percentile(d, 90):.4f} max {d.max():.3f}")
