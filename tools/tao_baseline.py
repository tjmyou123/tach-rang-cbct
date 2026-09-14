# -*- coding: utf-8 -*-
"""Tạo/cập nhật "đáp án" cho test hồi quy từ một thư mục kết quả ĐÃ DUYỆT.

    python tools/tao_baseline.py [thư_mục_kết_quả] [ca1 ca2 ...]

Mặc định: thư mục kết quả trong cấu hình (ket_qua), mọi ca có labelmaps/<ca>.json. Ghi tests/baseline/<ca>.json
gồm số voxel + thể tích mm³ từng vùng. Chỉ chạy lại khi đã KIỂM TRA BẰNG MẮT kết quả mới
và chấp nhận nó là chuẩn.
"""
import json
import sys
from pathlib import Path

import numpy as np
import SimpleITK as sitk

GOC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GOC))
from tachrang.core.pipeline import case_stem  # noqa: E402
from tachrang import cau_hinh  # noqa: E402


def thong_ke(lm_path: Path, js_path: Path) -> dict:
    img = sitk.ReadImage(str(lm_path))
    lab = sitk.GetArrayFromImage(img)
    sp = img.GetSpacing()
    vox_mm3 = float(sp[0] * sp[1] * sp[2])
    names = {int(k): v for k, v in json.loads(js_path.read_text(encoding="utf-8"))["labels"].items()}
    ids, dem = np.unique(lab, return_counts=True)
    vung = {}
    for i, n in zip(ids, dem):
        if i == 0:
            continue
        ten = names.get(int(i), f"label-{int(i)}")
        vung[ten] = {"id": int(i), "voxel": int(n), "mm3": round(float(n) * vox_mm3, 1)}
    so_fdi = sum(1 for t in vung if "FDI" in t.upper())
    return {"case": case_stem(lm_path), "shape_xyz": list(img.GetSize()),
            "spacing": [round(s, 4) for s in sp], "so_vung": len(vung),
            "so_rang_fdi": so_fdi, "vung": dict(sorted(vung.items()))}


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else cau_hinh.thu_muc_output()
    chon = set(sys.argv[2:])
    dich = GOC / "tests" / "baseline"
    dich.mkdir(parents=True, exist_ok=True)
    n = 0
    for js in sorted((out / "labelmaps").glob("*.json")):
        if ".lam-do" in js.name:
            continue
        case = js.name[:-5]
        if chon and case not in chon:
            continue
        lm = js.with_name(f"{case}.nii.gz")
        if not lm.is_file():
            continue
        tk = thong_ke(lm, js)
        tk["nguon"] = str(out.relative_to(GOC)) if out.is_relative_to(GOC) else str(out)
        (dich / f"{case}.json").write_text(json.dumps(tk, ensure_ascii=False, indent=1),
                                           encoding="utf-8")
        print(f"  {case}: {tk['so_vung']} vùng, {tk['so_rang_fdi']} răng FDI")
        n += 1
    print(f"Đã ghi {n} baseline vào {dich}")


if __name__ == "__main__":
    main()
