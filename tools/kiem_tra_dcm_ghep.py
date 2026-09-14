# -*- coding: utf-8 -*-
"""Kiểm tra DCM đã ghép: giải mã lại bằng hpsdecode, so với STL kèm, chụp ảnh răng gốc vs răng mới."""
import sys, re, base64
from pathlib import Path
import numpy as np
import vtk
from vtk.util.numpy_support import vtk_to_numpy
from hpsdecode import load_hps

GOC = Path(__file__).resolve().parents[1]
thu = Path(sys.argv[1]) if len(sys.argv) > 1 else GOC / "data_test/3shape_thu/1"
goc = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(r"C:\ProgramData\3Shape\OrthoData\1222\1")
rang = [int(x) for x in sys.argv[3].split(",")] if len(sys.argv) > 3 else [8, 14, 30]

for n in rang:
    f = thu / f"Tooth_{n}.dcm"
    pk, m = load_hps(str(f))
    s = f.read_bytes().decode("latin1")
    fc = int(re.search(r'facet_count="(\d+)"', s).group(1)); vc = int(re.search(r'vertex_count="(\d+)"', s).group(1))
    mb = base64.b64decode(re.search(r"<FacetMarks>([^<]*)</FacetMarks>", s).group(1))
    r = vtk.vtkSTLReader(); r.SetFileName(str(thu / "Models" / f"Tooth_{n}.stl")); r.Update()
    pd = r.GetOutput()
    fe = vtk.vtkFeatureEdges(); fe.SetInputData(pd); fe.BoundaryEdgesOn(); fe.FeatureEdgesOff(); fe.ManifoldEdgesOff(); fe.NonManifoldEdgesOn(); fe.Update()
    print(f"Tooth_{n}: schema {pk.schema} V {m.vertices.shape} F {m.faces.shape} | attr vertex_count {vc} facet_count {fc} | marks {len(mb)//4} "
          f"| STL tris {pd.GetNumberOfCells()} | cạnh biên/không-manifold: {fe.GetOutput().GetNumberOfCells()}")

# ảnh: răng gốc (trái) và răng mới (phải) cho răng đầu tiên trong danh sách
def actor(path, color, opacity=1.0):
    r = vtk.vtkSTLReader(); r.SetFileName(str(path)); r.Update()
    mp = vtk.vtkPolyDataMapper(); mp.SetInputConnection(r.GetOutputPort())
    a = vtk.vtkActor(); a.SetMapper(mp); a.GetProperty().SetColor(*color); a.GetProperty().SetOpacity(opacity)
    return a, r.GetOutput()

ren = vtk.vtkRenderer(); ren.SetBackground(1, 1, 1)
for k, n in enumerate(rang):
    a_goc, pd_goc = actor(goc / "Models" / f"Tooth_{n}.stl", (0.85, 0.85, 0.8))
    a_moi, pd_moi = actor(thu / "Models" / f"Tooth_{n}.stl", (0.95, 0.75, 0.3))
    b = pd_moi.GetBounds()
    dx = 14.0 * k
    a_goc.SetPosition(dx, 0, 0); a_moi.SetPosition(dx, 0, 0)
    a_goc.SetPosition(dx - 7 * 0, 0, 0)
    # đặt răng gốc lệch trái, răng mới lệch phải cùng cụm
    a_goc.AddPosition(-3.5, 0, 0); a_moi.AddPosition(3.5, 0, 0)
    ren.AddActor(a_goc); ren.AddActor(a_moi)
rw = vtk.vtkRenderWindow(); rw.SetOffScreenRendering(1); rw.SetSize(1600, 900); rw.AddRenderer(ren)
cam = ren.GetActiveCamera()
ren.ResetCamera()
b = ren.ComputeVisiblePropBounds()
c = [(b[0] + b[1]) / 2, (b[2] + b[3]) / 2, (b[4] + b[5]) / 2]
cam.SetFocalPoint(*c); cam.SetPosition(c[0], c[1], c[2] + 120); cam.SetViewUp(0, 1, 0)
ren.ResetCamera(); ren.ResetCameraClippingRange(); rw.Render()
w2i = vtk.vtkWindowToImageFilter(); w2i.SetInput(rw); w2i.Update()
wr = vtk.vtkPNGWriter(); p = GOC / "tests/anh/chan_rang_3shape_goc_vs_moi.png"; wr.SetFileName(str(p)); wr.SetInputData(w2i.GetOutput()); wr.Write()
print("->", p)
