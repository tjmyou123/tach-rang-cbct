import sys as _sys; from pathlib import Path as _P
GOC = _P(__file__).resolve().parents[1]; _sys.path.insert(0, str(GOC))  # gốc dự án
"""Chụp riêng từng STL của một ca (totalseg) để tìm mảng lạ."""
from pathlib import Path
import vtk

stl_dir = Path(str(GOC) + r"\thu_nghiem_totalseg\out\stl\Le-quang-tan-CTCB")
out_dir = Path(str(GOC) + r"\thu_nghiem_totalseg")

for name in ["Le-quang-tan-CTCB_lower-jawbone.stl", "Le-quang-tan-CTCB_crown.stl", "Le-quang-tan-CTCB_bridge.stl"]:
    f = stl_dir / name
    reader = vtk.vtkSTLReader()
    reader.SetFileName(str(f))
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputConnection(reader.GetOutputPort())
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    ren = vtk.vtkRenderer()
    ren.SetBackground(0.12, 0.12, 0.15)
    ren.AddActor(actor)
    rw = vtk.vtkRenderWindow()
    rw.SetOffScreenRendering(1)
    rw.SetSize(900, 700)
    rw.AddRenderer(ren)
    ren.ResetCamera()
    ren.GetActiveCamera().Azimuth(200)
    ren.GetActiveCamera().Elevation(-10)
    ren.ResetCameraClippingRange()
    rw.Render()
    w2i = vtk.vtkWindowToImageFilter()
    w2i.SetInput(rw)
    w2i.Update()
    writer = vtk.vtkPNGWriter()
    png = out_dir / (f.stem + ".png")
    writer.SetFileName(str(png))
    writer.SetInputConnection(w2i.GetOutputPort())
    writer.Write()
    print("Da luu:", png)
