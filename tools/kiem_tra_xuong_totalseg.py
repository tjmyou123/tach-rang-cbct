import sys as _sys; from pathlib import Path as _P
GOC = _P(__file__).resolve().parents[1]; _sys.path.insert(0, str(GOC))  # gốc dự án
"""Kiểm tra xương hàm dưới TotalSegmentator: chồng mask lên lát cắt CT."""
from pathlib import Path
import numpy as np
import SimpleITK as sitk
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ct_path = Path(str(GOC) + r"\thu_nghiem_totalseg\out\staged_inputs\Le-quang-tan-CTCB.nii.gz")
seg_dir = Path(str(GOC) + r"\thu_nghiem_totalseg\out\segmentations_totalseg\Le-quang-tan-CTCB")
out_png = Path(str(GOC) + r"\thu_nghiem_totalseg\kiem_tra_xuong_LQT_totalseg.png")

ct_img = sitk.ReadImage(str(ct_path))
ct = sitk.GetArrayFromImage(ct_img)  # z,y,x

low_img = sitk.ReadImage(str(seg_dir / "lower_jawbone.nii.gz"))
low = sitk.GetArrayFromImage(low_img).astype(bool)
up_img = sitk.ReadImage(str(seg_dir / "upper_jawbone.nii.gz"))
up = sitk.GetArrayFromImage(up_img).astype(bool)

print("CT shape:", ct.shape, "| lower vox:", low.sum(), "| upper vox:", up.sum())

# chọn các lát cắt có nhiều xương hàm dưới
zs = np.where(low.any(axis=(1, 2)))[0]
print("lower jawbone tren cac lat z:", zs.min(), "->", zs.max())
picks_z = np.linspace(zs.min(), zs.max(), 4).astype(int)

fig, axes = plt.subplots(2, 4, figsize=(20, 10))
for ax, z in zip(axes[0], picks_z):
    ax.imshow(ct[z], cmap="gray", vmin=-500, vmax=2500)
    ax.imshow(np.ma.masked_where(~low[z], low[z]), cmap="autumn", alpha=0.5)
    ax.imshow(np.ma.masked_where(~up[z], up[z]), cmap="winter", alpha=0.5)
    ax.set_title(f"axial z={z}")
    ax.axis("off")

# lát cắt đứng dọc giữa (sagittal) và trán (coronal)
xs = np.where(low.any(axis=(0, 1)))[0]
ys = np.where(low.any(axis=(0, 2)))[0]
picks = [("sagittal x", lambda i: (ct[:, :, i], low[:, :, i], up[:, :, i]), np.linspace(xs.min(), xs.max(), 2).astype(int)),
         ("coronal y", lambda i: (ct[:, i, :], low[:, i, :], up[:, i, :]), np.linspace(ys.min(), ys.max(), 2).astype(int))]
axi = 0
for name, getter, idxs in picks:
    for i in idxs:
        c, l, u = getter(int(i))
        ax = axes[1][axi]; axi += 1
        ax.imshow(c, cmap="gray", vmin=-500, vmax=2500, origin="lower")
        ax.imshow(np.ma.masked_where(~l, l), cmap="autumn", alpha=0.5, origin="lower")
        ax.imshow(np.ma.masked_where(~u, u), cmap="winter", alpha=0.5, origin="lower")
        ax.set_title(f"{name}={i}")
        ax.axis("off")

fig.suptitle("TotalSegmentator: do = xuong ham duoi, xanh = xuong ham tren")
fig.tight_layout()
fig.savefig(out_png, dpi=90)
print("Da luu:", out_png)
