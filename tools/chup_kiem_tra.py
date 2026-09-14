import sys as _sys; from pathlib import Path as _P
GOC = _P(__file__).resolve().parents[1]; _sys.path.insert(0, str(GOC))  # gốc dự án
"""Chụp ảnh 3D offscreen để kiểm tra kết quả STL."""
import sys
from pathlib import Path

from tachrang.ui.giao_dien import build_actors  # noqa: E402

import vtk  # noqa: E402

stl_dir = Path(str(GOC) + r"\thu_nghiem_totalseg\out\stl\Le-quang-tan-CTCB")
out_png = Path(str(GOC) + r"\thu_nghiem_totalseg\preview_LQT_totalseg.png")

ren = vtk.vtkRenderer()
ren.SetBackground(0.12, 0.12, 0.15)
actors = build_actors(stl_dir)
print("So actor:", len(actors), "| So STL:", len(list(stl_dir.glob('*.stl'))))
for actor in actors:
    ren.AddActor(actor)

rw = vtk.vtkRenderWindow()
rw.SetOffScreenRendering(1)
rw.SetSize(1200, 900)
rw.AddRenderer(ren)

ren.ResetCamera()
cam = ren.GetActiveCamera()
cam.Azimuth(200)   # nhìn từ phía trước
cam.Elevation(-10)
ren.ResetCameraClippingRange()
rw.Render()

w2i = vtk.vtkWindowToImageFilter()
w2i.SetInput(rw)
w2i.Update()
writer = vtk.vtkPNGWriter()
writer.SetFileName(str(out_png))
writer.SetInputConnection(w2i.GetOutputPort())
writer.Write()
print("Da luu:", out_png)
