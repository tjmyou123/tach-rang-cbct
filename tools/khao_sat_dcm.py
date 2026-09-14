# -*- coding: utf-8 -*-
"""Khảo sát định dạng .dcm (HPS) của 3Shape Ortho: giải mã Vertices, so với STL cùng răng."""
import base64, re, sys
from pathlib import Path
import numpy as np
D = Path(r"e:\dental segment\data_test\3shape_khao_sat")
name = sys.argv[1] if len(sys.argv) > 1 else "Tooth_8"
s = (D / f"{name}.dcm").read_bytes().decode("latin1")

def tag(t):
    m = re.search(rf"<{t}([^>]*)>([^<]*)</{t}>", s)
    return dict(re.findall(r'(\w+)="([^"]*)"', m.group(1))), base64.b64decode(m.group(2))

fa, fb = tag("Facets"); va, vb = tag("Vertices")
print("Facets attrs", fa, "bytes", len(fb)); print("Vertices attrs", va, "bytes", len(vb))
V = np.frombuffer(vb, dtype=np.float32).reshape(-1, 3)
print("V shape", V.shape, "min", V.min(0), "max", V.max(0))
print("facet bytes đầu:", fb[:64].hex())
print("facet bytes cuối:", fb[-32:].hex())
# phân bố giá trị byte
u, c = np.unique(np.frombuffer(fb, dtype=np.uint8), return_counts=True)
print("số byte khác nhau:", len(u), "top:", sorted(zip(c, u), reverse=True)[:12])
m = re.search(r"<FacetMarks>([^<]*)</FacetMarks>", s)
if m:
    mb = base64.b64decode(m.group(1)); print("FacetMarks bytes", len(mb), "đầu", mb[:32].hex())
    print("  marks/facet =", len(mb) / int(fa["facet_count"]))
# STL cùng tên
p = D / f"{name}.stl"
if p.exists():
    import vtk
    from vtk.util.numpy_support import vtk_to_numpy
    r = vtk.vtkSTLReader(); r.SetFileName(str(p)); r.Update()
    pd = r.GetOutput(); Vs = vtk_to_numpy(pd.GetPoints().GetData()); F = vtk_to_numpy(pd.GetPolys().GetData()).reshape(-1, 4)[:, 1:]
    print("STL: points", len(Vs), "tris", len(F))
    from scipy.spatial import cKDTree
    d, _ = cKDTree(V).query(Vs); print("  khoảng cách đỉnh STL→DCM: max", d.max())
    fe = vtk.vtkFeatureEdges(); fe.SetInputData(pd); fe.BoundaryEdgesOn(); fe.FeatureEdgesOff(); fe.ManifoldEdgesOff(); fe.NonManifoldEdgesOff(); fe.Update()
    print("  cạnh biên (hở):", fe.GetOutput().GetNumberOfCells(), "→", "KÍN" if fe.GetOutput().GetNumberOfCells() == 0 else "HỞ")
    print("  bbox STL", Vs.min(0), Vs.max(0))
