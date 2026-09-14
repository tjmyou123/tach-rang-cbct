#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test tự động giao diện chính: nạp DICOM 1 ca → chụp màn hình; thử nạp
thư mục nhiều ca → phải bị từ chối; thử zoom + đổi lát; công cụ sửa + đo.

Chạy tại gốc dự án:  python tests/test_giao_dien.py
Ảnh chụp ghi vào tests/anh/. Dữ liệu: CBCT_input/<ca> + ket_qua (đổi bằng TACHRANG_INPUT/OUTPUT)."""
import os
import sys
import faulthandler
import warnings
from pathlib import Path

faulthandler.enable()

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import vtk
vtk.vtkObject.GlobalWarningDisplayOff()
import vtkmodules.qt
vtkmodules.qt.PyQtImpl = "PySide6"
from PySide6 import QtCore, QtWidgets

from tachrang import cau_hinh
from tachrang.ui import giao_dien

_CFG = cau_hinh.doc_cau_hinh()
NHIEU_CA = str(_CFG["input_dir"])
# tên ca test lấy từ env hoặc file cục bộ tests/_ca_local.txt (không commit — dòng 1: tên ca, dòng 2: label)
_ca_local = Path(__file__).resolve().parent / "_ca_local.txt"
_dong = _ca_local.read_text(encoding="utf-8").splitlines() if _ca_local.exists() else []
CA_1 = os.environ.get("TACHRANG_TEST_CA") or str(_CFG["input_dir"] / (_dong[0] if _dong else "ca-mau"))
CA_LABEL = os.environ.get("TACHRANG_TEST_CA_LABEL") or (_dong[1] if len(_dong) > 1 else "ca-mau")
OUT = Path(__file__).resolve().parent / "anh"
OUT.mkdir(exist_ok=True)

# stdout của tiến trình GUI hay bị "nuốt" (QProcess con kế thừa) -> ghi thêm ra file
_LOG_F = open(OUT / "test_gd_log.txt", "w", encoding="utf-8")
_print = print


def print(*a, **k):  # noqa: A001
    _print(*a, **k)
    _print(*a, **k, file=_LOG_F)
    _LOG_F.flush()

ket_qua = {"canh_bao": None}

# Chặn hộp thoại chặn luồng trong test
def _warn(parent, title, text, *a, **k):
    print(f"[TEST] QMessageBox.warning: {title} | {text}")
    ket_qua["canh_bao"] = text
    return QtWidgets.QMessageBox.StandardButton.Ok
QtWidgets.QMessageBox.warning = staticmethod(_warn)
QtWidgets.QMessageBox.information = staticmethod(
    lambda *a, **k: print(f"[TEST] QMessageBox.information: {a[1] if len(a)>1 else ''}"))

real_exec = QtWidgets.QApplication.exec

def fake_exec(*args, **kwargs):
    app = QtWidgets.QApplication.instance()
    win = [w for w in app.topLevelWidgets() if isinstance(w, QtWidgets.QMainWindow)][0]

    def buoc1():
        print("[TEST] Nap thu muc NHIEU ca (phai bi tu choi)...")
        win.nap_dicom(NHIEU_CA)
        QtCore.QTimer.singleShot(700, cho_buoc1)

    def cho_buoc1():
        if win._dang_nap is not None or (win._loader and win._loader.isRunning()):
            QtCore.QTimer.singleShot(500, cho_buoc1)
            return
        if win.nguon.ct_u8 is None and ket_qua["canh_bao"]:
            print("[TEST] OK: nhieu ca bi tu choi dung nhu mong doi")
        else:
            print("[TEST] LOI: khong tu choi thu muc nhieu ca!")
        print("[TEST] Nap thu muc MOT ca...")
        win.nap_dicom(CA_1)
        QtCore.QTimer.singleShot(1000, cho_buoc2)

    def cho_buoc2():
        if win.nguon.ct_u8 is None:
            if win._dang_nap is None and not (win._loader and win._loader.isRunning()):
                print("[TEST] LOI: nap 1 ca that bai!")
                app.quit()
                return
            QtCore.QTimer.singleShot(700, cho_buoc2)
            return
        print(f"[TEST] Da nap: {win._ct_case}, shape={win.nguon.shape}")
        # thử zoom + đổi lát trên khung axial
        cv = win.canvases[0]
        cv._zoom_tai(QtCore.QPointF(cv.width() / 2, cv.height() / 2), 2.0)
        cv.set_k(cv.k + 25)
        v = cv._to_voxel(QtCore.QPointF(cv.width() / 2, cv.height() / 2))
        print(f"[TEST] zoom={cv.zoom:.2f}, lat={cv.k}, voxel giua khung={v}")
        QtCore.QTimer.singleShot(1500, chup)

    def chup():
        win.grab().save(str(OUT / "test_gd_main.png"))
        rw = win.vtk_widget.GetRenderWindow()

        def chup_3d(ten):
            w2i = vtk.vtkWindowToImageFilter()
            w2i.SetInput(rw)
            w2i.Update()
            pw = vtk.vtkPNGWriter()
            pw.SetFileName(str(OUT / ten))
            pw.SetInputConnection(w2i.GetOutputPort())
            pw.Write()
            print(f"[TEST] Da luu {ten}")

        chup_3d("test_gd_3d_xuongrang.png")          # kiểu 0: Xương + răng
        win.kieu_3d.setCurrentIndex(1)               # Chỉ răng (đặc)
        chup_3d("test_gd_3d_rang.png")
        win.kieu_3d.setCurrentIndex(2)               # Cả da/mô mềm
        chup_3d("test_gd_3d_momem.png")
        print(f"[TEST] nguong={win.sl_nguong.value()}, dam={win.sl_dam.value()}")

        # thử XOAY lát cắt: nghiêng axial 14 do -> cả 3 khung cập nhật
        cv0 = win.canvases[0]
        for _ in range(7):
            cv0._xoay(2.0)
        print(f"[TEST] goc xoay = {win.nguon.goc}")
        QtCore.QTimer.singleShot(800, chup_xoay)

    def chup_xoay():
        win.grab().save(str(OUT / "test_gd_xoay.png"))
        print("[TEST] Da luu test_gd_xoay.png")
        # nháy đúp: hết xoay
        win.canvases[0].mouseDoubleClickEvent(None)
        print(f"[TEST] sau nhay dup: goc = {win.nguon.goc}")
        buoc_dieu_huong()

    def buoc_dieu_huong():
        # bấm chuột trái giữa khung axial (che do xem) -> 2 khung kia doi lat
        cv = win.canvases[0]
        k1_truoc, k2_truoc = win.canvases[1].k, win.canvases[2].k
        cv._dieu_huong(QtCore.QPointF(cv.width() * 0.6, cv.height() * 0.6))
        print(f"[TEST] dieu huong: coronal {k1_truoc}->{win.canvases[1].k}, "
              f"sagittal {k2_truoc}->{win.canvases[2].k}")
        if (win.canvases[1].k, win.canvases[2].k) == (k1_truoc, k2_truoc):
            print("[TEST] LOI: dieu huong khong doi lat!")
        buoc_do()

    def buoc_do():
        # ĐO khoảng cách: 2 điểm cách nhau 100 px trên khung axial -> mm > 0
        cv = win.canvases[0]
        win.rb_do_kc.setChecked(True)
        p1 = QtCore.QPointF(cv.width() * 0.4, cv.height() * 0.5)
        p2 = QtCore.QPointF(cv.width() * 0.4 + 100, cv.height() * 0.5)
        cv._them_diem_do(p1)
        cv._them_diem_do(p2)
        ds = win.nguon.do_dac
        ok = bool(ds) and ds[-1]["gia_tri"] and ds[-1]["gia_tri"] > 0
        print(f"[TEST] do khoang cach: {ds[-1]['chu'] if ds else '?'} -> {'OK' if ok else 'LOI'}")
        # ĐO góc vuông: 3 điểm -> ~90°
        win.rb_do_goc.setChecked(True)
        c = QtCore.QPointF(cv.width() * 0.5, cv.height() * 0.5)
        cv._them_diem_do(QtCore.QPointF(c.x() + 80, c.y()))
        cv._them_diem_do(c)
        cv._them_diem_do(QtCore.QPointF(c.x(), c.y() - 80))
        g = win.nguon.do_dac[-1]["gia_tri"]
        print(f"[TEST] do goc vuong: {g:.1f} do -> {'OK' if abs(g - 90) < 1 else 'LOI'}")
        cv.grab().save(str(OUT / "test_gd_do.png"))
        win.rb_xem.setChecked(True)
        QtCore.QTimer.singleShot(300, buoc_sua)

    def buoc_sua():
        # nạp ca có labelmap trong ket_qua -> danh sach vung phai co
        out = Path(win.out_edit.text())
        print(f"[TEST] Mo ca {CA_LABEL} (labelmap co san)...")
        if not (out / "labelmaps" / f"{CA_LABEL}.nii.gz").is_file():
            print(f"[TEST] BO QUA buoc sua: khong co labelmaps/{CA_LABEL}.nii.gz")
            ket_thuc()
            return
        win.render_case(CA_LABEL)
        QtCore.QTimer.singleShot(2500, kiem_tra_sua)

    def kiem_tra_sua():
        n_vung = win.ds_vung.count()
        print(f"[TEST] danh sach vung: {n_vung} vung, lab is None? {win.lab is None}")
        ten_vung = [win.ds_vung.item(r).text() for r in range(min(n_vung, 40))]
        co_xoang = any("Xoang" in t for t in ten_vung)
        print(f"[TEST] co vung Xoang-ham? {co_xoang} | vd: {ten_vung[:6]}")
        if n_vung == 0 or win.lab is None:
            print("[TEST] LOI: khong nap duoc labelmap!")
            ket_thuc()
            return
        # tick an 1 vung -> vis_lut doi
        it0 = win.ds_vung.item(0)
        lid = it0.data(QtCore.Qt.ItemDataRole.UserRole)
        it0.setCheckState(QtCore.Qt.CheckState.Unchecked)
        print(f"[TEST] an vung id={lid}: vis_lut={bool(win.nguon.vis_lut[lid])} (mong False)")
        it0.setCheckState(QtCore.Qt.CheckState.Checked)
        # to ve: chon vung dau, bat To them, ve 1 net giua khung axial
        win.ds_vung.setCurrentItem(win.ds_vung.item(0))
        win.rb_to.setChecked(True)
        cv = win.canvases[0]
        truoc = int((win.lab == lid).sum())
        ev_pos = QtCore.QPointF(cv.width() / 2, cv.height() / 2)
        v = cv._to_voxel(ev_pos)
        if v is not None:
            win.bat_dau_net_ve(0, cv.k)
            win.to_tai(0, cv.k, v[0], v[1])
            sau = int((win.lab == lid).sum())
            print(f"[TEST] to ve: {truoc} -> {sau} voxel (mong tang)")
            win.hoan_tac()
            print(f"[TEST] hoan tac: {int((win.lab == lid).sum())} voxel (mong {truoc})")
        win.rb_xem.setChecked(True)
        # Công cụ thông minh (gọi thẳng thuật toán, không qua hộp thoại)
        from tachrang.core import sua_nhan
        import numpy as np
        rang = [i for i, nm in win.names.items() if "FDI" in nm]
        i_r = rang[0] if rang else lid
        t0 = int((win.lab == i_r).sum())
        kq = sua_nhan.lap_theo_nguong(win.lab, win.nguon.ct_u8, i_r,
                                      win.sl_nguong.value(), 2.0, win.nguon.sp)
        win._ap_ket_qua_sua(kq, "test lap")
        t1 = int((win.lab == i_r).sum())
        print(f"[TEST] lap theo nguong '{win.names[i_r]}': {t0} -> {t1} ({kq.ghi_chu})")
        kq2 = sua_nhan.lam_min_vung(win.lab, i_r, 0.4, win.nguon.sp)
        win._ap_ket_qua_sua(kq2, "test min")
        print(f"[TEST] lam min: {kq2.ghi_chu}")
        for _ in range(2):
            win.hoan_tac()
        t2 = int((win.lab == i_r).sum())
        print(f"[TEST] hoan tac 2 buoc: {t2} voxel -> {'OK' if t2 == t0 else 'LOI'}")
        kq3 = sua_nhan.moc_tu_hat(win.lab, win.nguon.ct_u8, win.sl_nguong.value(), 2.0,
                                  win.nguon.sp, chi_nhan=[i_r])
        win._ap_ket_qua_sua(kq3, "test moc")
        print(f"[TEST] moc tu hat (1 vung): {kq3.ghi_chu}")
        win.hoan_tac()
        print(f"[TEST] sau hoan tac: {int((win.lab == i_r).sum())} voxel (mong {t0})")
        QtCore.QTimer.singleShot(700, chup_sua)

    def chup_sua():
        win.grab().save(str(OUT / "test_gd_sua.png"))
        print("[TEST] Da luu test_gd_sua.png")
        ket_thuc()

    def ket_thuc():
        print("[TEST] HOAN TAT")
        app.quit()

    QtCore.QTimer.singleShot(1200, buoc1)
    QtCore.QTimer.singleShot(240_000, lambda: (print("[TEST] QUA GIO"), app.quit()))
    return real_exec()

QtWidgets.QApplication.exec = fake_exec
giao_dien.run_gui()
