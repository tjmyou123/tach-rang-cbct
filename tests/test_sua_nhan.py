# -*- coding: utf-8 -*-
"""Unit test thuật toán sửa nhãn (dữ liệu tổng hợp, chạy < 1s, không cần GPU/dữ liệu).
Chạy:  python -m unittest tests.test_sua_nhan -v   (tại gốc dự án)"""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tachrang.core import sua_nhan  # noqa: E402
from tachrang import nhat_ky  # noqa: E402

SP = (0.5, 0.5, 0.5)   # mm (sx, sy, sz)


def _khoi():
    """CT: 2 'răng' sáng cách nhau 1 khe tối 2 voxel; nhãn 1 chỉ phủ NỬA răng trái."""
    ct = np.zeros((30, 30, 60), np.uint8)
    ct[5:25, 5:25, 5:25] = 200          # răng trái (x 5..24)
    ct[5:25, 5:25, 27:47] = 200         # răng phải (x 27..46), khe tối x 25,26
    lab = np.zeros(ct.shape, np.int16)
    lab[5:25, 5:25, 5:15] = 1           # nửa trái răng trái
    lab[5:25, 5:25, 40:47] = 2          # mép phải răng phải
    return ct, lab


class TestLapTheoNguong(unittest.TestCase):
    def test_lan_trong_khoi_khong_qua_khe(self):
        ct, lab = _khoi()
        kq = sua_nhan.lap_theo_nguong(lab, ct, 1, 120, 20.0, SP)
        self.assertGreater(kq.so_voxel, 0)
        # phủ hết răng trái ...
        self.assertTrue((lab[5:25, 5:25, 5:25] == 1).all())
        # ... nhưng không vượt khe tối sang răng phải
        self.assertFalse((lab[:, :, 27:] == 1).any())
        self.assertEqual(kq.nhan, {1})
        sua_nhan.hoan_tac(lab, kq)
        self.assertEqual(int((lab == 1).sum()), 20 * 20 * 10)

    def test_gioi_han_ban_kinh(self):
        ct, lab = _khoi()
        kq = sua_nhan.lap_theo_nguong(lab, ct, 1, 120, 1.0, SP)   # 1mm = 2 voxel
        self.assertTrue((lab[5:25, 5:25, 15:17] == 1).all())
        self.assertFalse((lab[:, :, 18:] == 1).any())
        self.assertEqual(kq.so_voxel, 20 * 20 * 2)

    def test_khong_de_len_nhan_khac(self):
        ct, lab = _khoi()
        lab[5:25, 5:25, 15:25] = 3
        kq = sua_nhan.lap_theo_nguong(lab, ct, 1, 120, 20.0, SP)
        self.assertEqual(kq.net, [])
        self.assertTrue((lab[5:25, 5:25, 15:25] == 3).all())


class TestLamMin(unittest.TestCase):
    def test_bo_gai_va_hoan_tac(self):
        _, lab = _khoi()
        lab[:] = 0
        lab[10:20, 10:20, 10:20] = 1
        lab[15, 15, 20:26] = 1          # gai 1 voxel
        goc = lab.copy()
        kq = sua_nhan.lam_min_vung(lab, 1, 0.6, SP)
        self.assertLess(kq.so_voxel, 0)
        self.assertFalse(lab[15, 15, 23:26].any())
        self.assertTrue((lab[12:18, 12:18, 12:18] == 1).all())
        sua_nhan.hoan_tac(lab, kq)
        np.testing.assert_array_equal(lab, goc)

    def test_khong_lan_sang_vung_khac(self):
        _, lab = _khoi()
        lab[:] = 0
        lab[10:20, 10:20, 10:20] = 1
        lab[10:20, 10:20, 20:30] = 2
        sua_nhan.lam_min_vung(lab, 1, 1.0, SP)
        self.assertTrue((lab[10:20, 10:20, 20:30] == 2).all())


class TestMocTuHat(unittest.TestCase):
    def test_gan_cho_nhan_gan_nhat(self):
        ct, lab = _khoi()
        kq = sua_nhan.moc_tu_hat(lab, ct, 120, 30.0, SP)
        self.assertTrue((lab[5:25, 5:25, 5:25] == 1).all())
        self.assertTrue((lab[5:25, 5:25, 27:47] == 2).all())
        self.assertEqual(kq.nhan, {1, 2})

    def test_bo_nhan(self):
        ct, lab = _khoi()
        sua_nhan.moc_tu_hat(lab, ct, 120, 30.0, SP, bo_nhan=(2,))
        self.assertTrue((lab[5:25, 5:25, 5:25] == 1).all())
        self.assertFalse((lab[5:25, 5:25, 27:40] > 0).any())

    def test_chi_nhan(self):
        ct, lab = _khoi()
        sua_nhan.moc_tu_hat(lab, ct, 120, 30.0, SP, chi_nhan=[2])
        self.assertTrue((lab[5:25, 5:25, 27:47] == 2).all())
        self.assertFalse((lab[5:25, 5:25, 15:25] > 0).any())


class TestNhatKy(unittest.TestCase):
    def test_giai_thich(self):
        self.assertIn("RAM", nhat_ky.giai_thich(MemoryError()))
        self.assertIn("VRAM", nhat_ky.giai_thich(RuntimeError("CUDA out of memory")))
        self.assertIn("thư viện", nhat_ky.giai_thich(ImportError("No module named x")))
        self.assertIn("DICOM", nhat_ky.giai_thich(RuntimeError("ITK ExceptionObject GDCM")))

    def test_tach_loi(self):
        cau, duong = nhat_ky.tach_loi_tu_log("abc\n[LOI] Hết RAM\n[LOI-LOG] C:/x.log\n")
        self.assertEqual((cau, duong), ("Hết RAM", "C:/x.log"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
