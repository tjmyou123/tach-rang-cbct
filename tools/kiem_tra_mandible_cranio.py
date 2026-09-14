import sys as _sys; from pathlib import Path as _P
GOC = _P(__file__).resolve().parents[1]; _sys.path.insert(0, str(GOC))  # gốc dự án
"""Kiểm tra mandible từ task craniofacial_structures."""
from pathlib import Path
import numpy as np
import SimpleITK as sitk
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ct_path = Path(str(GOC) + r"\thu_nghiem_totalseg\out\staged_inputs\Le-quang-tan-CTCB.nii.gz")
seg_dir = Path(str(GOC) + r"\thu_nghiem_totalseg\out_cranio")
out_png = Path(str(GOC) + r"\thu_nghiem_totalseg\kiem_tra_mandible_cranio.png")

ct = sitk.GetArrayFromImage(sitk.ReadImage(str(ct_path)))
man = sitk.GetArrayFromImage(sitk.ReadImage(str(seg_dir / "mandible.nii.gz"))).astype(bool)
tlow = sitk.GetArrayFromImage(sitk.ReadImage(str(seg_dir / "teeth_lower.nii.gz"))).astype(bool)
print("mandible vox:", man.sum(), "| teeth_lower vox:", tlow.sum())

zs = np.where(man.any(axis=(1, 2)))[0]
print("mandible z:", zs.min(), "->", zs.max())
picks_z = np.linspace(zs.min(), zs.max(), 4).astype(int)

fig, axes = plt.subplots(2, 4, figsize=(20, 10))
for ax, z in zip(axes[0], picks_z):
    ax.imshow(ct[z], cmap="gray", vmin=-500, vmax=2500)
    ax.imshow(np.ma.masked_where(~man[z], man[z]), cmap="autumn", alpha=0.5)
    ax.imshow(np.ma.masked_where(~tlow[z], tlow[z]), cmap="winter", alpha=0.5)
    ax.set_title(f"axial z={z}")
    ax.axis("off")

xs = np.where(man.any(axis=(0, 1)))[0]
ys = np.where(man.any(axis=(0, 2)))[0]
picks = [("sagittal x", np.linspace(xs.min(), xs.max(), 2).astype(int)),
         ("coronal y", np.linspace(ys.min(), ys.max(), 2).astype(int))]
axi = 0
for i in picks[0][1]:
    ax = axes[1][axi]; axi += 1
    ax.imshow(ct[:, :, int(i)], cmap="gray", vmin=-500, vmax=2500, origin="lower")
    ax.imshow(np.ma.masked_where(~man[:, :, int(i)], man[:, :, int(i)]), cmap="autumn", alpha=0.5, origin="lower")
    ax.set_title(f"sagittal x={i}")
    ax.axis("off")
for i in picks[1][1]:
    ax = axes[1][axi]; axi += 1
    ax.imshow(ct[:, int(i), :], cmap="gray", vmin=-500, vmax=2500, origin="lower")
    ax.imshow(np.ma.masked_where(~man[:, int(i), :], man[:, int(i), :]), cmap="autumn", alpha=0.5, origin="lower")
    ax.set_title(f"coronal y={i}")
    ax.axis("off")

fig.suptitle("craniofacial_structures: do = mandible, xanh = rang duoi")
fig.tight_layout()
fig.savefig(out_png, dpi=90)
print("Da luu:", out_png)
