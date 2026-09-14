# -*- coding: utf-8 -*-
"""Chụp ảnh kiểm tra hàm lai: scan gốc vs hàm lai (nướu xám, răng theo màu)."""
import sys
from pathlib import Path
import numpy as np
import vtk

GOC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GOC))
from tachrang.core.ham_lai import _doc_polydata

case = sys.argv[1] if len(sys.argv) > 1 else "DICOM-000000000024-20220917150728"
ham = sys.argv[2] if len(sys.argv) > 2 else "tren"
d = GOC / "ket_qua" / "stl" / case / "ham-lai"
f = d / f"{case}_Ham-{ham}_lai-3shape.stl"
pd = _doc_polydata(f)

# tách shell để tô màu: nướu = shell lớn nhất
conn = vtk.vtkPolyDataConnectivityFilter()
conn.SetInputData(pd)
conn.SetExtractionModeToAllRegions()
conn.ColorRegionsOn()
conn.Update()
out = conn.GetOutput()
n_reg = conn.GetNumberOfExtractedRegions()
sizes = np.array([conn.GetRegionSizes().GetValue(i) for i in range(n_reg)])
print("shells:", n_reg, "lớn nhất:", sizes.max(), "tổng tam giác:", pd.GetNumberOfCells())

lut = vtk.vtkLookupTable()
lut.SetNumberOfTableValues(n_reg)
rng = np.random.RandomState(3)
for i in range(n_reg):
    if i == int(sizes.argmax()):
        lut.SetTableValue(i, 0.85, 0.72, 0.68, 1.0)
    else:
        c = rng.uniform(0.3, 1.0, 3)
        lut.SetTableValue(i, c[0], c[1], c[2], 1.0)
lut.Build()

mp = vtk.vtkPolyDataMapper()
mp.SetInputData(out)
mp.SetScalarModeToUsePointData()
mp.SetLookupTable(lut)
mp.SetScalarRange(0, n_reg - 1)
act = vtk.vtkActor()
act.SetMapper(mp)

ren = vtk.vtkRenderer()
ren.SetBackground(1, 1, 1)
ren.AddActor(act)
rw = vtk.vtkRenderWindow()
rw.SetOffScreenRendering(1)
rw.SetSize(1400, 900)
rw.AddRenderer(ren)

def chup(ten, vi_tri, len_):
    cam = ren.GetActiveCamera()
    b = out.GetBounds()
    c = [(b[0] + b[1]) / 2, (b[2] + b[3]) / 2, (b[4] + b[5]) / 2]
    cam.SetFocalPoint(*c)
    cam.SetPosition(c[0] + vi_tri[0], c[1] + vi_tri[1], c[2] + vi_tri[2])
    cam.SetViewUp(*len_)
    ren.ResetCamera()
    ren.ResetCameraClippingRange()
    rw.Render()
    w2i = vtk.vtkWindowToImageFilter()
    w2i.SetInput(rw)
    w2i.Update()
    wr = vtk.vtkPNGWriter()
    p = GOC / "tests" / "anh" / f"ham_lai_{ham}_{ten}.png"
    wr.SetFileName(str(p))
    wr.SetInputData(w2i.GetOutput())
    wr.Write()
    print("->", p)

# hệ scan 3Shape: thường z hướng lên (mặt nhai hàm trên hướng -z)
chup("mat_nhai", (0, 0, -200 if ham == "tren" else 200), (0, 1, 0))
chup("day", (0, 0, 200 if ham == "tren" else -200), (0, 1, 0))
chup("truoc", (0, -200, 0), (0, 0, 1))
chup("ben", (200, 0, 0), (0, 0, 1))

# cận cảnh răng cửa (FDI11/41) nhìn từ phía môi
import json
from tachrang.core.ham_lai import _pd_sang_numpy, _bien_doi
kq = json.loads(f.with_suffix(".json").read_text(encoding="utf-8"))
Ti = np.array(kq["T_cbct_sang_scan"])
stl_dir = d.parent
tam = {}
for r in kq["rang"]:
    V, _ = _pd_sang_numpy(_doc_polydata(stl_dir / f"{r}.stl"))
    tam[r] = _bien_doi(V, Ti).mean(axis=0)
c_arch = np.mean(list(tam.values()), axis=0)
r11 = [r for r in tam if "FDI11" in r or "FDI41" in r][0]
lab = tam[r11] - c_arch
lab[1] = 0            # bỏ thành phần trục mặt nhai (y)
lab /= np.linalg.norm(lab)
cam = ren.GetActiveCamera()
cam.SetFocalPoint(*tam[r11])
cam.SetPosition(*(tam[r11] + lab * 60))
cam.SetViewUp(0, -1 if ham == "tren" else 1, 0)
ren.ResetCameraClippingRange()
cam.SetParallelProjection(True)
cam.SetParallelScale(9)
rw.Render()
w2i = vtk.vtkWindowToImageFilter(); w2i.SetInput(rw); w2i.Update()
wr = vtk.vtkPNGWriter(); p = GOC / "tests" / "anh" / f"ham_lai_{ham}_can_canh.png"
wr.SetFileName(str(p)); wr.SetInputData(w2i.GetOutput()); wr.Write(); print("->", p)
