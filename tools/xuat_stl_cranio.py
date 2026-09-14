import sys as _sys; from pathlib import Path as _P
GOC = _P(__file__).resolve().parents[1]; _sys.path.insert(0, str(GOC))  # gốc dự án
"""Tạo STL xương hàm dưới trọn vẹn từ task craniofacial_structures và chụp ảnh."""
import sys
from pathlib import Path
import numpy as np
import SimpleITK as sitk
import vtk

from tachrang.core.pipeline import physical_matrix, mask_to_stl  # noqa: E402

seg_dir = Path(str(GOC) + r"\thu_nghiem_totalseg\out_cranio")
out_dir = Path(str(GOC) + r"\thu_nghiem_totalseg\stl_cranio")
out_dir.mkdir(parents=True, exist_ok=True)

for name in ["mandible", "teeth_lower", "sinus_maxillary"]:
    img = sitk.ReadImage(str(seg_dir / f"{name}.nii.gz"))
    arr = sitk.GetArrayFromImage(img).astype(np.uint8)
    if arr.sum() == 0:
        print(f"{name}: rong, bo qua")
        continue
    stl = out_dir / f"Le-quang-tan_{name}.stl"
    n_tri, vol = mask_to_stl(arr, (0, 0, 0), physical_matrix(img), stl,
                             smooth_iterations=25, passband=0.05, decimate=0.6)
    print(f"{name}: {n_tri} tam giac, {vol:.0f} mm3 -> {stl.name}")

# chụp ảnh mandible
reader = vtk.vtkSTLReader()
reader.SetFileName(str(out_dir / "Le-quang-tan_mandible.stl"))
mapper = vtk.vtkPolyDataMapper(); mapper.SetInputConnection(reader.GetOutputPort())
actor = vtk.vtkActor(); actor.SetMapper(mapper)
actor.GetProperty().SetColor(0.9, 0.87, 0.8)
ren = vtk.vtkRenderer(); ren.SetBackground(0.12, 0.12, 0.15); ren.AddActor(actor)
rw = vtk.vtkRenderWindow(); rw.SetOffScreenRendering(1); rw.SetSize(1100, 800); rw.AddRenderer(ren)
ren.ResetCamera()
cam = ren.GetActiveCamera(); cam.Azimuth(200); cam.Elevation(-15)
ren.ResetCameraClippingRange(); rw.Render()
w2i = vtk.vtkWindowToImageFilter(); w2i.SetInput(rw); w2i.Update()
w = vtk.vtkPNGWriter(); png = out_dir.parent / "preview_mandible_cranio.png"
w.SetFileName(str(png)); w.SetInputConnection(w2i.GetOutputPort()); w.Write()
print("Da luu:", png)
