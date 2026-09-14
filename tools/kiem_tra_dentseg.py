import sys as _sys; from pathlib import Path as _P
GOC = _P(__file__).resolve().parents[1]; _sys.path.insert(0, str(GOC))  # gốc dự án
"""Kiểm tra DentalSegmentator trên một ca: lát cắt + ảnh 3D."""
import sys
from pathlib import Path
import numpy as np
import SimpleITK as sitk
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import vtk

from tachrang.ui.giao_dien import build_actors  # noqa: E402

ct_path = Path(str(GOC) + r"\thu_nghiem_dentseg\staged_inputs\Le-quang-tan-CTCB.nii.gz")
seg_path = Path(str(GOC) + r"\thu_nghiem_dentseg\segmentations_dentseg\Le-quang-tan-CTCB.nii.gz")
out_dir = Path(str(GOC) + r"\thu_nghiem_dentseg")

ct = sitk.GetArrayFromImage(sitk.ReadImage(str(ct_path)))
seg = sitk.GetArrayFromImage(sitk.ReadImage(str(seg_path)))
u, c = np.unique(seg, return_counts=True)
print("nhan:", {int(l): int(n) for l, n in zip(u, c) if l > 0})

man = seg == 2
up = seg == 1
zs = np.where(man.any(axis=(1, 2)))[0]
picks_z = np.linspace(zs.min(), zs.max(), 4).astype(int)

fig, axes = plt.subplots(2, 4, figsize=(20, 10))
for ax, z in zip(axes[0], picks_z):
    ax.imshow(ct[z], cmap="gray", vmin=-500, vmax=2500)
    ax.imshow(np.ma.masked_where(~man[z], man[z]), cmap="autumn", alpha=0.5)
    ax.imshow(np.ma.masked_where(~up[z], up[z]), cmap="winter", alpha=0.5)
    ax.set_title(f"axial z={z}")
    ax.axis("off")
xs = np.where(man.any(axis=(0, 1)))[0]
ys = np.where(man.any(axis=(0, 2)))[0]
for ax, i in zip(axes[1][:2], np.linspace(xs.min(), xs.max(), 2).astype(int)):
    ax.imshow(ct[:, :, int(i)], cmap="gray", vmin=-500, vmax=2500, origin="lower")
    ax.imshow(np.ma.masked_where(~man[:, :, int(i)], man[:, :, int(i)]), cmap="autumn", alpha=0.5, origin="lower")
    ax.imshow(np.ma.masked_where(~up[:, :, int(i)], up[:, :, int(i)]), cmap="winter", alpha=0.5, origin="lower")
    ax.set_title(f"sagittal x={i}")
    ax.axis("off")
for ax, i in zip(axes[1][2:], np.linspace(ys.min(), ys.max(), 2).astype(int)):
    ax.imshow(ct[:, int(i), :], cmap="gray", vmin=-500, vmax=2500, origin="lower")
    ax.imshow(np.ma.masked_where(~man[:, int(i), :], man[:, int(i), :]), cmap="autumn", alpha=0.5, origin="lower")
    ax.imshow(np.ma.masked_where(~up[:, int(i), :], up[:, int(i), :]), cmap="winter", alpha=0.5, origin="lower")
    ax.set_title(f"coronal y={i}")
    ax.axis("off")
fig.suptitle("DentalSegmentator: do = Mandible, xanh = Upper Skull/Maxilla")
fig.tight_layout()
fig.savefig(out_dir / "kiem_tra_dentseg_LQT.png", dpi=90)
print("Da luu:", out_dir / "kiem_tra_dentseg_LQT.png")

# 3D
ren = vtk.vtkRenderer()
ren.SetBackground(0.12, 0.12, 0.15)
for a in build_actors(Path(str(GOC) + r"\thu_nghiem_dentseg\stl\Le-quang-tan-CTCB")):
    ren.AddActor(a)
rw = vtk.vtkRenderWindow()
rw.SetOffScreenRendering(1)
rw.SetSize(1100, 800)
rw.AddRenderer(ren)
ren.ResetCamera()
ren.GetActiveCamera().Azimuth(200)
ren.GetActiveCamera().Elevation(-10)
ren.ResetCameraClippingRange()
rw.Render()
w2i = vtk.vtkWindowToImageFilter()
w2i.SetInput(rw)
w2i.Update()
w = vtk.vtkPNGWriter()
w.SetFileName(str(out_dir / "preview_dentseg_LQT.png"))
w.SetInputConnection(w2i.GetOutputPort())
w.Write()
print("Da luu:", out_dir / "preview_dentseg_LQT.png")
