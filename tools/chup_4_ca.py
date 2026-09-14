import sys as _sys; from pathlib import Path as _P
GOC = _P(__file__).resolve().parents[1]; _sys.path.insert(0, str(GOC))  # gốc dự án
"""Chụp preview 3D cho các ca trong ket_qua_totalseg."""
import sys
from pathlib import Path

from tachrang.ui.giao_dien import build_actors  # noqa: E402
import vtk  # noqa: E402

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(str(GOC) + r"\ket_qua_totalseg\stl")
for case_dir in sorted(d for d in root.iterdir() if d.is_dir()):
    ren = vtk.vtkRenderer()
    ren.SetBackground(0.12, 0.12, 0.15)
    for a in build_actors(case_dir):
        ren.AddActor(a)
    rw = vtk.vtkRenderWindow()
    rw.SetOffScreenRendering(1)
    rw.SetSize(1000, 800)
    rw.AddRenderer(ren)
    ren.ResetCamera()
    cam = ren.GetActiveCamera()
    cam.Azimuth(200)
    cam.Elevation(-10)
    ren.ResetCameraClippingRange()
    rw.Render()
    w2i = vtk.vtkWindowToImageFilter()
    w2i.SetInput(rw)
    w2i.Update()
    writer = vtk.vtkPNGWriter()
    png = root.parent / f"preview_{case_dir.name}.png"
    writer.SetFileName(str(png))
    writer.SetInputConnection(w2i.GetOutputPort())
    writer.Write()
    print("Da luu:", png)
