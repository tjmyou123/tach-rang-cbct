import sys as _sys; from pathlib import Path as _P
GOC = _P(__file__).resolve().parents[1]; _sys.path.insert(0, str(GOC))  # gốc dự án
"""Thí nghiệm: hiệu chỉnh thang cường độ về dạng HU rồi để AI chạy lại."""
import numpy as np
import SimpleITK as sitk
from pathlib import Path

src = Path(str(GOC) + r"\ket_qua\staged_inputs\ngo-quang-hoan.nii.gz")
out_dir = Path(str(GOC) + r"\thu_nghiem_fix\input")
out_dir.mkdir(parents=True, exist_ok=True)

img = sitk.ReadImage(str(src))
a = sitk.GetArrayFromImage(img).astype(np.float32)

p05, p995 = np.percentile(a, [0.5, 99.5])
print(f"truoc: min={a.min():.0f} max={a.max():.0f} p0.5={p05:.0f} p99.5={p995:.0f}")

# Ép về thang HU quen thuộc: [p0.5 .. p99.5] -> [-1000 .. 3000]
a = np.clip(a, p05, p995)
a = (a - p05) / (p995 - p05) * 4000.0 - 1000.0
print(f"sau:   min={a.min():.0f} max={a.max():.0f}")

fixed = sitk.GetImageFromArray(a.astype(np.int16))
fixed.CopyInformation(img)
sitk.WriteImage(fixed, str(out_dir / "ngo-quang-hoan-FIXINT.nii.gz"))
print("Da ghi:", out_dir / "ngo-quang-hoan-FIXINT.nii.gz")
