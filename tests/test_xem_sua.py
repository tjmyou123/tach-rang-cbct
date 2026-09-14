"""Test tự động cửa sổ Xem & Sửa: mở, tô thử, chụp ảnh, xuất 1 STL.
Chạy: python tests/test_xem_sua.py [thư_mục_kết_quả] [tên_ca]"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6 import QtCore, QtWidgets  # noqa: E402

app = QtWidgets.QApplication(sys.argv)

from tachrang import cau_hinh  # noqa: E402
from tachrang.ui.xem_sua import CuaSoXemSua  # noqa: E402

ANH = Path(__file__).resolve().parent / "anh"
ANH.mkdir(exist_ok=True)
out = Path(sys.argv[1]) if len(sys.argv) > 1 else cau_hinh.goc_du_an() / "ket_qua_combo"
case = sys.argv[2] if len(sys.argv) > 2 else "Le-quang-tan-CTCB"
w = CuaSoXemSua(out / "staged_inputs" / f"{case}.nii.gz",
                out / "labelmaps" / f"{case}.nii.gz",
                out / "labelmaps" / f"{case}.json",
                out / "stl" / case, case)
w.show()

shots = []

def buoc1():
    # chụp sau khi 3D dựng xong
    p = ANH / "test_xemsua_1.png"
    w.grab().save(str(p))
    shots.append(p)
    print("da chup:", p)
    # thử tô: chọn chế độ tô, vẽ 1 nét vào giữa lát axial
    w.rb_to.setChecked(True)
    w.list.setCurrentRow(1)  # Mandible
    cv = w.canvases[0]
    w.bat_dau_net_ve(0, cv.k)
    for d in range(0, 30, 3):
        w.to_tai(0, cv.k, 300, 250 + d)
    print("da to thu 1 net, undo stack:", len(w.undo_stack))
    w.hoan_tac()
    print("da hoan tac OK")
    # bật CBCT mờ trong 3D
    w.cb_ct3d.setChecked(True)
    QtCore.QTimer.singleShot(2500, buoc2)

def buoc2():
    p = ANH / "test_xemsua_2.png"
    w.grab().save(str(p))
    print("da chup:", p)
    # chụp riêng khung 3D qua VTK (grab của Qt không chụp được OpenGL)
    import vtk
    w2i = vtk.vtkWindowToImageFilter()
    w2i.SetInput(w.vtk_widget.GetRenderWindow())
    w2i.Update()
    wr = vtk.vtkPNGWriter()
    wr.SetFileName(str(ANH / "test_xemsua_3d.png"))
    wr.SetInputConnection(w2i.GetOutputPort())
    wr.Write()
    print("da chup 3D: test_xemsua_3d.png")
    QtCore.QTimer.singleShot(400, buoc3)

def buoc3():
    app.closeAllWindows()
    app.quit()

QtCore.QTimer.singleShot(9000, buoc1)
# chặn hộp thoại thông báo khi xuất xong bằng cách auto-accept
def auto_close():
    for tw in app.topLevelWidgets():
        if isinstance(tw, QtWidgets.QMessageBox):
            tw.accept()
timer = QtCore.QTimer()
timer.timeout.connect(auto_close)
timer.start(500)

app.exec()
print("TEST XONG")
