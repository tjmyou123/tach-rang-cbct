import sys as _sys; from pathlib import Path as _P
GOC = _P(__file__).resolve().parents[1]; _sys.path.insert(0, str(GOC))  # gốc dự án
"""Soi nhãn xương hàm của một ca: 53=Mandible (đỏ), 54=Maxilla (xanh)."""
import SimpleITK as sitk
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

name = "Le-quang-tan-CTCB"
img = sitk.ReadImage(str(GOC) + rf"\ket_qua\staged_inputs\{name}.nii.gz")
a = sitk.GetArrayFromImage(img)
seg = sitk.GetArrayFromImage(
    sitk.ReadImage(str(GOC) + rf"\ket_qua\segmentations\{name}.nii.gz"))

# Chỉ giữ 2 nhãn xương: 53 -> 1 (đỏ), 54 -> 2 (xanh)
bones = np.zeros_like(seg)
bones[seg == 53] = 1
bones[seg == 54] = 2
cmap = ListedColormap([(1, 0, 0, 0.55), (0, 0.5, 1, 0.55)])

zs = [a.shape[0] // 4, a.shape[0] // 2, 3 * a.shape[0] // 4]
ys = [a.shape[1] // 2]
fig, axes = plt.subplots(2, 3, figsize=(15, 10))
for i, z in enumerate(zs):
    axes[0, i].imshow(a[z], cmap="gray")
    m = np.ma.masked_where(bones[z] == 0, bones[z])
    axes[0, i].imshow(m, cmap=cmap, vmin=1, vmax=2)
    axes[0, i].set_title(f"axial z={z}  (do=HamDuoi, xanh=HamTren)")
    axes[0, i].axis("off")
# coronal + sagittal
y = a.shape[1] // 2
axes[1, 0].imshow(a[:, y, :], cmap="gray", origin="lower")
m = np.ma.masked_where(bones[:, y, :] == 0, bones[:, y, :])
axes[1, 0].imshow(m, cmap=cmap, vmin=1, vmax=2, origin="lower")
axes[1, 0].set_title("coronal")
axes[1, 0].axis("off")
x = a.shape[2] // 2
axes[1, 1].imshow(a[:, :, x], cmap="gray", origin="lower")
m = np.ma.masked_where(bones[:, :, x] == 0, bones[:, :, x])
axes[1, 1].imshow(m, cmap=cmap, vmin=1, vmax=2, origin="lower")
axes[1, 1].set_title("sagittal")
axes[1, 1].axis("off")
axes[1, 2].axis("off")
plt.tight_layout()
plt.savefig(str(GOC) + r"\ket_qua\kiem_tra_xuong_LQT.png", dpi=80)
print("OK")
