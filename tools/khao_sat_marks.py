# -*- coding: utf-8 -*-
"""Phân tích FacetMarks của Tooth_N.dcm: giá trị nào ứng với thân răng scan / chân ảo?"""
import base64, re, sys
from pathlib import Path
import numpy as np
from hpsdecode import load_hps
D = Path(r"e:\dental segment\data_test\3shape_khao_sat")
name = sys.argv[1] if len(sys.argv) > 1 else "Tooth_8"
p = D / f"{name}.dcm"
packed, mesh = load_hps(str(p))
V, F = mesh.vertices, mesh.faces
print(name, "schema", packed.schema, "V", V.shape, "F", F.shape)
s = p.read_bytes().decode("latin1")
m = re.search(r"<FacetMarks>([^<]*)</FacetMarks>", s)
mb = base64.b64decode(m.group(1))
marks = np.frombuffer(mb, dtype=np.uint32)
print("marks", marks.shape, "unique:", [(hex(u), int(c)) for u, c in zip(*np.unique(marks, return_counts=True))])
# cũng thử 2 x uint16
m16 = np.frombuffer(mb, dtype=np.uint16).reshape(-1, 2)
print("uint16 cột0 unique", np.unique(m16[:, 0]), "cột1 unique", [(hex(u), int(c)) for u, c in zip(*np.unique(m16[:, 1], return_counts=True))])
# vị trí trọng tâm theo mark (y là trục dọc theo bbox: y 10.4..20.6)
C = V[F].mean(axis=1)
for u in np.unique(marks):
    sel = marks == u
    print(f"  mark {u:#010x}: n={sel.sum():5d}  tâm y trung bình {C[sel,1].mean():6.2f}  y min {C[sel,1].min():6.2f} max {C[sel,1].max():6.2f}  z tb {C[sel,2].mean():6.2f}")
# so thứ tự facets DCM với STL
import vtk
from vtk.util.numpy_support import vtk_to_numpy
r = vtk.vtkSTLReader(); r.SetFileName(str(D / f"{name}.stl")); r.Update()
pd = r.GetOutput(); Vs = vtk_to_numpy(pd.GetPoints().GetData()); Fs = vtk_to_numpy(pd.GetPolys().GetData()).reshape(-1, 4)[:, 1:]
Cs = Vs[Fs].mean(axis=1)
print("tâm facet DCM vs STL cùng thứ tự: max lệch", np.abs(C - Cs).max())
np.save(D / f"{name}_marks.npy", marks)
