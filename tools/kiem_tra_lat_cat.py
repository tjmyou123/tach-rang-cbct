import sys as _sys; from pathlib import Path as _P
GOC = _P(__file__).resolve().parents[1]; _sys.path.insert(0, str(GOC))  # gốc dự án
import SimpleITK as sitk
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

names = ["LE-DINH-LY-1967-DICOM", "Le-quang-tan-CTCB", "ngo-quang-hoan"]
fig, axes = plt.subplots(3, 3, figsize=(13, 13))
for r, name in enumerate(names):
    img = sitk.ReadImage(str(GOC) + rf"\ket_qua\staged_inputs\{name}.nii.gz")
    a = sitk.GetArrayFromImage(img)  # z,y,x
    seg = sitk.GetArrayFromImage(
        sitk.ReadImage(str(GOC) + rf"\ket_qua\segmentations\{name}.nii.gz"))
    zc, yc, xc = [s // 2 for s in a.shape]
    axes[r, 0].imshow(a[zc], cmap="gray")
    axes[r, 0].set_title(f"{name[:18]} axial")
    axes[r, 1].imshow(a[:, yc, :], cmap="gray", origin="lower")
    axes[r, 1].set_title("coronal")
    axes[r, 2].imshow(a[:, yc, :], cmap="gray", origin="lower")
    s2 = seg[:, yc, :]
    axes[r, 2].imshow(np.ma.masked_where(s2 == 0, s2), cmap="jet", alpha=0.5,
                      origin="lower", vmin=1, vmax=55)
    axes[r, 2].set_title("seg overlay")
    for ax in axes[r]:
        ax.axis("off")
plt.tight_layout()
plt.savefig(str(GOC) + r"\ket_qua\kiem_tra_lat_cat.png", dpi=80)
print("OK")
