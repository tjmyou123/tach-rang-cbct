# -*- coding: utf-8 -*-
"""Test HỒI QUY trên ca thật: so kết quả hiện tại với đáp án đã duyệt (tests/baseline/).

    python -m unittest tests.test_hoi_quy -v
    TACHRANG_KET_QUA=<thư mục kết quả khác>  để so một lần chạy mới (mặc định: thư mục kết quả trong cấu hình)

Mỗi ca là 1 subTest; ca không có dữ liệu -> bỏ qua (skip), không fail.
Tiêu chí (chỉnh ở DUNG_SAI):
  - số răng FDI và TẬP tên răng FDI giống baseline
  - thể tích từng vùng lệch không quá: răng 10%, xương 3%, ống TK/xoang/khác 15%
  - số vùng tổng không lệch quá 2 (Rang-them/Rang-ngam có thể dao động)
"""
import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tachrang import cau_hinh  # noqa: E402

GOC = Path(__file__).resolve().parents[1]
BASELINE = Path(__file__).resolve().parent / "baseline"
KET_QUA = Path(os.environ.get("TACHRANG_KET_QUA") or cau_hinh.thu_muc_output())
DUNG_SAI = {"rang": 0.10, "xuong": 0.03, "khac": 0.15}
LECH_SO_VUNG = 2


def loai(ten: str) -> str:
    t = ten.lower()
    if "fdi" in t or "rang" in t:
        return "rang"
    if any(k in t for k in ("mandible", "maxilla", "skull", "jawbone")):
        return "xuong"
    return "khac"


def _thong_ke_hien_tai(case: str):
    from tools.tao_baseline import thong_ke
    lm = KET_QUA / "labelmaps" / f"{case}.nii.gz"
    js = KET_QUA / "labelmaps" / f"{case}.json"
    if not (lm.is_file() and js.is_file()):
        return None
    return thong_ke(lm, js)


class TestHoiQuy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baselines = sorted(BASELINE.glob("*.json"))
        if not cls.baselines:
            raise unittest.SkipTest("Chưa có tests/baseline/*.json — chạy tools/tao_baseline.py")

    def test_tung_ca(self):
        so_ca = 0
        for bf in self.baselines:
            goc = json.loads(bf.read_text(encoding="utf-8"))
            case = goc["case"]
            hien = _thong_ke_hien_tai(case)
            if hien is None:
                print(f"  [skip] {case}: không có labelmaps trong {KET_QUA}")
                continue
            so_ca += 1
            with self.subTest(ca=case):
                self.assertEqual(hien["shape_xyz"], goc["shape_xyz"], "kích thước ảnh khác")
                fdi_goc = {t for t in goc["vung"] if "FDI" in t.upper()}
                fdi_hien = {t for t in hien["vung"] if "FDI" in t.upper()}
                self.assertEqual(hien["so_rang_fdi"], goc["so_rang_fdi"],
                                 f"số răng FDI: {hien['so_rang_fdi']} vs {goc['so_rang_fdi']}")
                self.assertEqual(fdi_hien, fdi_goc,
                                 f"thiếu {sorted(fdi_goc - fdi_hien)} / thừa {sorted(fdi_hien - fdi_goc)}")
                self.assertLessEqual(abs(hien["so_vung"] - goc["so_vung"]), LECH_SO_VUNG,
                                     f"số vùng {hien['so_vung']} vs {goc['so_vung']}")
                loi = []
                for ten, v in goc["vung"].items():
                    if ten not in hien["vung"]:
                        if loai(ten) != "rang":     # Rang-them/ngam cho phép đổi tên
                            loi.append(f"mất vùng {ten}")
                        continue
                    a, b = hien["vung"][ten]["mm3"], v["mm3"]
                    ts = DUNG_SAI[loai(ten)]
                    if b > 0 and abs(a - b) / b > ts:
                        loi.append(f"{ten}: {a:.0f} vs {b:.0f} mm³ ({(a - b) / b * 100:+.1f}% > {ts * 100:.0f}%)")
                self.assertEqual(loi, [], "\n" + "\n".join(loi))
        if so_ca == 0:
            self.skipTest(f"Không ca nào có dữ liệu trong {KET_QUA}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
