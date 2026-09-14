# -*- coding: utf-8 -*-
"""Kiểm tra nhanh GUI panel ⑤ 3Shape (cùng cách test_giao_dien.py: chặn exec, chạy trong cửa sổ thật).
Chạy tại gốc dự án: python tests/test_gd_3shape.py — log ghi tests/anh/test_gd_3shape_log.txt"""
import os, sys
from pathlib import Path
GOC = Path(__file__).resolve().parents[1]
os.chdir(GOC)
sys.path.insert(0, str(GOC))
import vtk
vtk.vtkObject.GlobalWarningDisplayOff()
import vtkmodules.qt
vtkmodules.qt.PyQtImpl = "PySide6"
from PySide6 import QtCore, QtWidgets
from tachrang.ui import giao_dien

OUT = GOC / "tests" / "anh"
log = []


def ghi(s):
    log.append(s)
    (OUT / "test_gd_3shape_log.txt").write_text("\n".join(log), encoding="utf-8")


QtWidgets.QMessageBox.information = staticmethod(lambda *a, **k: ghi(f"INFO: {a[1]} | {a[2][:80]}"))
QtWidgets.QMessageBox.warning = staticmethod(lambda *a, **k: ghi(f"WARN: {a[1]} | {a[2][:80]}"))
QtWidgets.QMessageBox.question = staticmethod(
    lambda *a, **k: (ghi(f"QUESTION: {a[1]}"), QtWidgets.QMessageBox.StandardButton.No)[1])
ms = r"C:\ProgramData\3Shape\OrthoData\1222\1"
QtWidgets.QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: ms)
real_exec = QtWidgets.QApplication.exec


def fake_exec(*args, **kwargs):
    app = QtWidgets.QApplication.instance()
    w = [x for x in app.topLevelWidgets() if isinstance(x, QtWidgets.QMainWindow)][0]

    def chay():
        try:
            for ten in ("tabs_trai", "tab_3shape", "cay_kho", "kho_tim", "btn_kho_goiy", "spin_gap",
                        "btn_3s_ghep", "btn_3s_khoiphuc", "lb_3s", "lb_ms_chon"):
                ghi(f"{ten}: {'OK' if hasattr(w, ten) else 'THIEU'}")
            ghi(f"tab: {[w.tabs_trai.tabText(i) for i in range(w.tabs_trai.count())]}")
            bar = w.tabs_trai.tabBar()
            [bar.setTabVisible(i, True) for i in range(bar.count())]   # phòng user đã ẩn tab (QSettings)
            w.tabs_trai.setCurrentWidget(w.tab_3shape)   # -> tự nạp kho
            app.processEvents()
            ghi(f"kho thậ t: {len(w._kho_bn)} BN; lb_3s={w.lb_3s.text()[:80]}")
            # kho thủ = junction tới backup răng CA gốc (kho thậ t đã bị 3Shape mã hóa 1 phần sau khi lưu setup)
            w.kho_edit.setText(str(GOC / "data_test" / "kho_test"))
            w.nap_kho_3shape()
            ghi(f"kho: {len(w._kho_bn)} BN; cây top={w.cay_kho.topLevelItemCount()}; lb_3s={w.lb_3s.text()[:80]}")
            w._ca_hien = "DICOM-000000000024-20220917150728"
            w._da_nap = r"E:\dental segment\CBCT_input\HO THI THU HUONG"
            w._goi_y_benh_nhan()
            ghi(f"gợi ý: {w.lb_3s.text()[:100]}")
            ms = w._ms_dang_chon()
            ghi(f"model set đang chọn: {ms['duong_dan'] if ms else None} (răng {ms['so_rang'] if ms else '-'})")
            ghi(f"lb_ms_chon: {w.lb_ms_chon.text()[:120]}")
            w.kho_tim.setText("khongco")
            ghi(f"lọc 'khongco' ẩn: {w.cay_kho.topLevelItem(0).isHidden()} (mong True)")
            w.kho_tim.setText("huon")
            ghi(f"lọc 'huon' ẩn: {w.cay_kho.topLevelItem(0).isHidden()} (mong False)")
            # kết quả ca: ket_qua (nếu đã có scan căn) hoặc bản backup đủ dữ liệu (khi user đang test lại từ đầu)
            out = GOC / "ket_qua"
            case_dir = out / "stl" / "DICOM-000000000024-20220917150728"
            if not list(case_dir.glob("*_can-CBCT.json")):
                bk = sorted((GOC / "backup_ketqua").glob("*/stl/DICOM-000000000024-20220917150728"))
                bk_can = [b for b in bk if list(b.glob("*_can-CBCT.json"))]   # ưu tiên bản có scan đã căn
                if bk_can or bk:
                    out = (bk_can or bk)[-1].parents[1]
            w.out_edit.setText(str(out))
            w._orthoanalyzer_dang_mo = lambda p: True
            w.ghep_3shape()                      # -> WARN đang mở
            # scan thô của ca KHÁC không được dính theo khi render ca này
            it = QtWidgets.QListWidgetItem("x")
            it.setFlags(it.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(QtCore.Qt.CheckState.Checked)
            it.setData(QtCore.Qt.ItemDataRole.UserRole, "fake")
            w.ds_scan.addItem(it)
            w._scan_items["fake"] = {"actor": vtk.vtkActor(), "item": it, "da_can": False,
                                     "info": {}, "pd": None, "lat": None, "case": "CA-KHAC"}
            w.render_case("DICOM-000000000024-20220917150728")
            ghi(f"scan thô ca khác còn lại: {'fake' in w._scan_items} (mong False)")
            ghi(f"scan đã căn nạp lại: {sum(1 for d in w._scan_items.values() if d['da_can'])}")
            # bug cũ: bỏ scan khi có viền scan KHÁC KÍCH THƯỚC đứng trước trong nguon.scans
            # → 'in'/'remove' so == qua dict chứa mảng numpy → ValueError broadcast
            import numpy as _np
            w.nguon.scans.insert(0, {"V": _np.zeros((5, 3, 3)), "mau": (1, 2, 3), "hien": False})
            ps = [p for p, d in w._scan_items.items() if d["da_can"]]
            if ps:
                w._scan_bo_file(ps[0])
                ghi(f"bỏ scan đã căn (viền khác cỡ đứng trước): OK, còn {len(w.nguon.scans)} viền")
            ghi(f"tab idx sau bỏ scan: {w.tabs_trai.currentIndex()}")
            w.tabs_trai.setCurrentWidget(w.tab_3shape)
            app.processEvents()
            ghi(f"tab idx sau switch 3shape: {w.tabs_trai.currentIndex()}")
            # ── đối chiếu & xem trước (chạy luồng nền -> chờ) ──
            w._goi_y_benh_nhan(im_lang=True)
            w._3s_doi_chieu()

            def cho_doi_chieu(lan=0):
                if w._3s_thread is not None and w._3s_thread.isRunning():
                    if lan < 240:
                        QtCore.QTimer.singleShot(500, lambda: cho_doi_chieu(lan + 1))
                        return
                    ghi("TIMEOUT đối chiếu")
                    app.quit(); return
                # sau doi_chieu_xong, luồng ghép thủ có thể đang chạy tiếp -> chờ tới khi có lớp 'ghep'
                if not w._3s_actors["ghep"]:
                    if lan < 240:
                        QtCore.QTimer.singleShot(500, lambda: cho_doi_chieu(lan + 1))
                        return
                app.processEvents()
                ghi(f"tab idx trước bảng: {w.tabs_trai.currentIndex()}")
                ghi(f"bảng cặp: {w.bang_cap.rowCount()} dòng; lb_3s = {w.lb_3s.text()[:90]}")
                cap = w._3s_cap_tu_bang() or {}
                ghi(f"cặp tự động: {sum(1 for v in cap.values() if v)} ghép, {sum(1 for v in cap.values() if v is None)} bỏ")
                ghi(f"lớp 3D: 3shape={len(w._3s_actors['3shape'])} cbct={len(w._3s_actors['cbct'])} ghep={len(w._3s_actors['ghep'])}")
                # đổi thủ công 1 cặp -> bỏ qua, xem cột Trùng
                cb0 = w.bang_cap.cellWidget(0, 1)
                if cb0 is not None:
                    cb0.setCurrentIndex(0)
                    ghi(f"đổi dòng 0 thành bỏ qua → cột Trùng = {w.bang_cap.item(0, 2).text()}; lb = {w.lb_3s.text()[:60]}")
                else:
                    ghi("dòng 0 không có combo (dữ liệu thiếu?) — bỏ qua bước đổi cặp")
                w.bang_cap.setCurrentCell(3, 0); w.cb_chi_rang_chon.setChecked(True); app.processEvents()
                n3 = w._3s_rang_chon()
                hien = [k for k, a in w._3s_actors['ghep'].items() if a.GetVisibility()]
                ghi(f"chọn dòng 3 (răng {n3}), chỉ răng chọn → răng ghép đang hiện: {hien} (mong [{n3}])")
                w.cb_chi_rang_chon.setChecked(False); w.cb_lop_cbct.setChecked(False); app.processEvents()
                # tắt nốt 2 lớp còn lại -> mọi răng phải ẩn, kể cả răng CBCT không có cặp (vd răng khôn)
                w.cb_lop_3s.setChecked(False); w.cb_lop_ghep.setChecked(False); app.processEvents()
                con = sum(1 for d in w._3s_actors.values() for a in d.values() if a.GetVisibility())
                con += sum(1 for k, a in w._stl_actors.items()
                           if ("fdi" in k or "rang" in k) and a.GetVisibility())
                ghi(f"tắt hết 3 lớp → răng còn hiện: {con} (mong 0)")
                w.cb_lop_3s.setChecked(True); w.cb_lop_ghep.setChecked(True); app.processEvents()
                ghi(f"chế độ chỉ 3D: lát cắt ẩn={not w.hang_tren.isVisible() and not w._o_lat[2].isVisible()} (mong True); "
                    f"khung 3D rộng={w.vtk_widget.width()}x{w.vtk_widget.height()}")
                w.grab().save(str(OUT / "test_gd_3shape.png"))
                w.tabs_trai.setCurrentIndex(0); app.processEvents()
                ghi(f"về tab tách răng: lát cắt hiện lại={w.hang_tren.isVisible() and w._o_lat[2].isVisible()} (mong True)")
                # tách lớp: về tab tách răng phải TRẢ LẠI lớp của ca, ẩn lớp xem trước 3shape
                rang_ca = sum(1 for k, a in w._stl_actors.items() if ("fdi" in k or "rang" in k) and a.GetVisibility())
                lop_3s = sum(1 for d in w._3s_actors.values() for a in d.values() if a.GetVisibility())
                ghi(f"về tab tách răng: răng của ca hiện lại={rang_ca} (mong >0); lớp xem trước còn hiện={lop_3s} (mong 0)")
                w.tabs_trai.setCurrentWidget(w.tab_3shape); app.processEvents()
                rang_ca2 = sum(1 for k, a in w._stl_actors.items() if ("fdi" in k or "rang" in k) and a.GetVisibility())
                ghi(f"quay lại 3shape: răng của ca đã ẩn={rang_ca2 == 0} (mong True)")
                w2i = vtk.vtkWindowToImageFilter(); w2i.SetInput(w.vtk_widget.GetRenderWindow()); w2i.Update()
                wr = vtk.vtkPNGWriter(); wr.SetFileName(str(OUT / "test_gd_3shape_3d.png")); wr.SetInputData(w2i.GetOutput()); wr.Write()
                ghi("DONE")
                app.quit()
            QtCore.QTimer.singleShot(500, cho_doi_chieu)
            return
        except Exception:
            import traceback
            ghi("LOI: " + traceback.format_exc())
            app.quit()
    QtCore.QTimer.singleShot(1500, chay)
    return real_exec()          # PySide6: QApplication.exec() là hàm tĩnh, KHÔNG nhậ n đối số


QtWidgets.QApplication.exec = fake_exec
giao_dien.run_gui()
