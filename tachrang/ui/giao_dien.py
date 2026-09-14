#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
giao_dien.py — Giao diện kiểu 3D Slicer cho tachrang.core.pipeline

Bố cục: panel điều khiển bên trái, KHUNG XEM 3D NHÚNG bên phải.
Sau khi tách xong, kết quả tự động hiển thị trong khung 3D (không cần bấm gì);
đổi ca bệnh trong ô chọn là khung 3D đổi theo.

Chạy:  python -m tachrang        (hoặc double-click TachRang.bat)
"""

import json
import os
import re
import subprocess
import sys
import time
import traceback
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")  # chặn các cảnh báo vô hại bật thành popup vtkOutputWindow

from tachrang import cau_hinh, nhat_ky  # noqa: E402

GOC = cau_hinh.goc_du_an()
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def lenh_pipeline():
    """(chương trình, [tham số đầu]) để chạy pipeline ở tiến trình con."""
    if getattr(sys, "frozen", False):
        return sys.executable, ["--pipeline"]
    return sys.executable, ["-m", "tachrang.core.pipeline"]

# Nhận dạng tiến độ từ output của pipeline
RE_NCASES = re.compile(r"^\s*(\d+) ca: (.+)$", re.M)          # "3 ca: A, B, C"
RE_TQDM = re.compile(r"(\d+)%\|[^|]*\|\s*(\d+)/(\d+)")        # thanh tqdm "n/m"
RE_SPLIT_CASE = re.compile(r"^  ([^\s:][^:\n]*):\s*$", re.M)  # "  ten-ca:" khi tách STL
RE_STL_ADD = re.compile(r"^\s*\+\s+(\S+\.stl)\b", re.M)       # "    + file.stl (...)"
RE_TACH_CA = re.compile(r"\[tach-ca\]\s*(\d+)/(\d+)")          # "[tach-ca] 2/3"
RE_TACH = re.compile(r"\[tach\]\s*(\d+)%\s*—\s*(.+)$", re.M)    # "[tach]  45% — việc"
PHAN_AI = 0.85        # phần thanh tiến trình dành cho AI; còn lại cho bước tách răng

# Bảng màu phân biệt các răng (dùng chung tông với lát cắt — xem xem_sua.PALETTE)
PALETTE = [
    (0.90, 0.10, 0.29), (0.24, 0.71, 0.29), (1.00, 0.88, 0.10), (0.00, 0.51, 0.78),
    (0.96, 0.51, 0.19), (0.57, 0.12, 0.71), (0.27, 0.94, 0.94), (0.94, 0.20, 0.90),
    (0.82, 0.96, 0.24), (0.98, 0.75, 0.83), (0.00, 0.50, 0.50), (0.86, 0.75, 1.00),
    (0.67, 0.43, 0.16), (1.00, 0.98, 0.78), (0.50, 0.00, 0.00), (0.67, 1.00, 0.76),
    (0.50, 0.50, 0.00), (1.00, 0.84, 0.71), (0.25, 0.35, 1.00), (1.00, 0.41, 0.38),
    (0.39, 0.86, 0.24), (1.00, 0.63, 0.00), (0.35, 0.24, 0.86), (0.00, 0.78, 0.63),
    (0.90, 0.35, 0.55), (0.55, 0.78, 1.00), (0.78, 0.63, 0.35), (0.63, 0.24, 0.39),
    (0.24, 0.55, 0.24), (1.00, 0.51, 0.82), (0.59, 0.90, 0.78), (0.71, 0.35, 0.16),
    (0.43, 0.43, 1.00), (0.86, 0.86, 0.35), (0.16, 0.71, 0.86), (0.78, 0.24, 0.24),
    (0.47, 0.71, 0.12), (0.98, 0.55, 0.47), (0.51, 0.31, 0.63), (0.35, 0.63, 0.47),
]
TRANSLUCENT_KEYS = ("mandible", "maxilla", "jawbone", "canal", "pharynx",
                    "skull", "implant", "bridge", "crown", "head")

# Giao diện SÁNG, tông ẤM (cam đất) — không dùng màu xanh
STYLE = """
* { font-family: 'Segoe UI'; font-size: 10pt; color: #33291f; }
QMainWindow, QWidget { background: #f6f2ec; }
QGroupBox { background: #fffdf9; border: 1px solid #e3d9ca; border-radius: 10px;
            margin-top: 14px; padding: 6px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 6px;
                   color: #b95d1a; font-weight: 600; }
QLabel { background: transparent; }
QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox {
    background: #ffffff; border: 1px solid #ddd0bd; border-radius: 6px;
    padding: 4px 8px; selection-background-color: #f0b27a;
    selection-color: #33291f; }
QLineEdit:focus, QComboBox:focus { border: 1px solid #e08b3d; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView { background: #fffdf9; border: 1px solid #ddd0bd;
                              selection-background-color: #fbe3cb; }
QPushButton { background: #fdf8f1; border: 1px solid #d9cbb6; border-radius: 8px;
              padding: 6px 12px; }
QPushButton:hover { background: #fbeedd; border: 1px solid #e0a566; }
QPushButton:pressed { background: #f3e2cb; }
QPushButton:disabled { color: #b8a88f; background: #f4ede2; }
QPushButton#run { background: #e07b2e; border: none; font-weight: 700;
                  color: #ffffff; padding: 8px 12px; }
QPushButton#run:hover { background: #ef8c3f; }
QPushButton#run:disabled { background: #edcdaa; color: #a98f6f; }
QPushButton#stop { background: #f8e2e0; border: 1px solid #e2b0ac; color: #a33b31; }
QPushButton#stop:hover { background: #f5d2cf; }
QListWidget { background: #ffffff; border: 1px solid #ddd0bd; border-radius: 8px;
              alternate-background-color: #faf5ed; }
QListWidget::item { padding: 3px 4px; border-radius: 4px; }
QListWidget::item:selected { background: #f0a94e; color: #3a2410; font-weight: 600; }
QListWidget::item:hover { background: #fbe8cf; }
QRadioButton, QCheckBox { spacing: 6px; background: transparent; }
QCheckBox::indicator, QListWidget::indicator {
    width: 17px; height: 17px; border: 2px solid #b89873;
    border-radius: 4px; background: #ffffff; }
QCheckBox::indicator:hover, QListWidget::indicator:hover { border-color: #e07b2e; }
QCheckBox::indicator:checked, QListWidget::indicator:checked {
    background: #e07b2e; border: 2px solid #a8500f; image: url("__CHECK__"); }
QCheckBox::indicator:unchecked, QListWidget::indicator:unchecked { background: #ffffff; }
QCheckBox::indicator:indeterminate, QListWidget::indicator:indeterminate {
    background: #f3c48a; border: 2px solid #b95d1a; }
QRadioButton::indicator { width: 17px; height: 17px; border: 2px solid #b89873;
    border-radius: 10px; background: #ffffff; }
QRadioButton::indicator:hover { border-color: #e07b2e; }
QRadioButton::indicator:checked { background: qradialgradient(cx:0.5, cy:0.5,
    radius:0.5, fx:0.5, fy:0.5, stop:0 #ffffff, stop:0.35 #ffffff,
    stop:0.45 #e07b2e, stop:1 #e07b2e); border: 2px solid #a8500f; }
QSlider::groove:horizontal { height: 5px; background: #e5dac8; border-radius: 2px; }
QSlider::handle:horizontal { width: 14px; margin: -5px 0; border-radius: 7px;
                             background: #e07b2e; }
QSlider::handle:horizontal:hover { background: #f09a52; }
QSlider::sub-page:horizontal { background: #eda75f; border-radius: 2px; }
QProgressBar { background: #ffffff; border: 1px solid #ddd0bd; border-radius: 7px;
               text-align: center; min-height: 16px; color: #7a5a33; }
QProgressBar::chunk { background: #eda75f; border-radius: 6px; }
QPlainTextEdit { border: 1px solid #ddd0bd; border-radius: 8px; }
QSplitter::handle { background: #f6f2ec; }
QSplitter::handle:hover { background: #eda75f; }
QStatusBar { background: #efe8dd; color: #7a6a52; }
QScrollBar:vertical { background: transparent; width: 10px; }
QScrollBar::handle:vertical { background: #d9cbb6; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #c4b298; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: transparent; height: 10px; }
QScrollBar::handle:horizontal { background: #d9cbb6; border-radius: 5px; min-width: 30px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QTabWidget::pane { border: none; border-top: 2px solid #e3d9ca; }
QTabBar { background: transparent; }
QTabBar::tab { background: transparent; color: #8a7660; border: none;
               border-bottom: 3px solid transparent; padding: 6px 12px;
               margin: 0 1px; font-weight: 600; }
QTabBar::tab:hover:!selected { color: #b95d1a; background: #f7efe3;
               border-top-left-radius: 8px; border-top-right-radius: 8px; }
QTabBar::tab:selected { color: #b95d1a; border-bottom: 3px solid #e07b2e; }
QMenu { background: #fffdf9; border: 1px solid #ddd0bd; border-radius: 8px; padding: 4px; }
QMenu::item { padding: 5px 24px 5px 8px; border-radius: 5px; background: transparent; }
QMenu::item:selected { background: #fbe3cb; }
QMenu::item:disabled { color: #b8a88f; }
QMenu::separator { height: 1px; background: #e3d9ca; margin: 4px 6px; }
QMenu::indicator { width: 17px; height: 17px; border: 2px solid #b89873;
                   border-radius: 4px; background: #ffffff; margin-left: 3px; }
QMenu::indicator:checked { background: #e07b2e; border: 2px solid #a8500f;
                           image: url("__CHECK__"); }
QToolButton#nut_tab_menu { border: none; background: transparent; color: #8a7660;
                           padding: 2px 9px; font-size: 13pt; border-radius: 6px; }
QToolButton#nut_tab_menu:hover { background: #f7efe3; color: #b95d1a; }
QToolButton#nut_tab_menu::menu-indicator { image: none; }
QToolTip { background: #fffdf9; color: #33291f; border: 1px solid #e08b3d;
           padding: 4px; }
"""


def khoa_ten(s: str) -> str:
    """Khóa so khớp tên file/nhãn: mọi ký tự đặc biệt quy về '-' để '_' và '-'
    không làm lệch (ví dụ 'FDI23_upper-left-canine' khớp tên file dùng '_')."""
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def _tao_anh_tick() -> str:
    """Vẽ dấu tích trắng lưu ra PNG tạm, trả URL để QSS tô vào ô đã tích
    (theme sáng khiến ô tích cũ khó nhìn — dấu tích trắng trên nền cam rõ hẳn)."""
    import tempfile
    from PySide6 import QtCore, QtGui
    px = QtGui.QPixmap(17, 17)
    px.fill(QtGui.QColor(0, 0, 0, 0))
    p = QtGui.QPainter(px)
    p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
    pen = QtGui.QPen(QtGui.QColor("#ffffff"))
    pen.setWidthF(2.4)
    pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(QtCore.Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.drawPolyline(QtGui.QPolygonF([
        QtCore.QPointF(3.5, 9.0), QtCore.QPointF(7.0, 12.5),
        QtCore.QPointF(13.5, 4.5)]))
    p.end()
    duong = os.path.join(tempfile.gettempdir(), "dental_tick.png")
    px.save(duong)
    return duong.replace("\\", "/")


def actor_for_stl(path: Path, tooth_i: int):
    """Tạo 1 actor VTK cho 1 file STL với màu theo loại cấu trúc.
    Trả về (actor, tooth_i mới)."""
    import vtk

    reader = vtk.vtkSTLReader()
    reader.SetFileName(str(path))
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputConnection(reader.GetOutputPort())
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)

    name = Path(path).stem.lower()
    prop = actor.GetProperty()
    if "sinus" in name or "xoang" in name:
        prop.SetColor(0.30, 0.60, 1.00)
        prop.SetOpacity(0.50)
    elif "pulp" in name or "-tuy" in name:
        prop.SetColor(1.00, 0.15, 0.15)
    elif "mandible" in name or "jawbone" in name:
        prop.SetColor(0.69, 0.74, 0.78)     # hàm dưới: xám đá lạnh
        prop.SetOpacity(0.35)
    elif "maxilla" in name or "skull" in name:
        prop.SetColor(0.91, 0.83, 0.67)     # hàm trên/sọ: be cát ấm
        prop.SetOpacity(0.35)
    elif any(k in name for k in TRANSLUCENT_KEYS):
        prop.SetColor(0.87, 0.86, 0.80)
        prop.SetOpacity(0.35)
    else:
        prop.SetColor(*PALETTE[tooth_i % len(PALETTE)])
        tooth_i += 1
    prop.SetSpecular(0.25)
    prop.SetSpecularPower(20)
    return actor, tooth_i


def build_actors(stl_dir: Path):
    """Tạo danh sách actor VTK từ các file STL của một ca (răng màu riêng,
    xoang hàm xanh trong mờ, xương xám mờ, tủy đỏ)."""
    actors = []
    tooth_i = 0
    for f in sorted(Path(stl_dir).glob("*.stl")):
        actor, tooth_i = actor_for_stl(f, tooth_i)
        actors.append(actor)
    return actors


def show_preview(stl_dir: Path):
    """Chế độ --preview: mở cửa sổ VTK độc lập (giữ để tương thích)."""
    import vtk

    actors = build_actors(stl_dir)
    if not actors:
        print(f"Không có file STL trong {stl_dir}")
        return
    renderer = vtk.vtkRenderer()
    renderer.GradientBackgroundOn()
    renderer.SetBackground(0.09, 0.11, 0.14)
    renderer.SetBackground2(0.25, 0.28, 0.32)
    for a in actors:
        renderer.AddActor(a)
    window = vtk.vtkRenderWindow()
    window.AddRenderer(renderer)
    window.SetSize(1050, 780)
    window.SetWindowName(f"Preview 3D — {Path(stl_dir).name}")
    interactor = vtk.vtkRenderWindowInteractor()
    interactor.SetRenderWindow(window)
    interactor.SetInteractorStyle(vtk.vtkInteractorStyleTrackballCamera())
    renderer.ResetCamera()
    window.Render()
    interactor.Start()


# ────────────────────────────── GUI (Qt + VTK nhúng) ───────────────────────────

def run_gui():
    import vtk  # noqa: F401 — đăng ký factory OpenGL trước khi tạo widget
    vtk.vtkObject.GlobalWarningDisplayOff()  # không bật cửa sổ vtkOutputWindow
    from PySide6 import QtCore, QtGui, QtWidgets
    import vtkmodules.qt
    vtkmodules.qt.PyQtImpl = "PySide6"
    from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
    import numpy as np
    from tachrang.ui import khung_xem
    from tachrang.core import sua_nhan

    class NguonSua(khung_xem.NguonXem):
        """Nguồn xem + TÔ VẺ, nối với các nút của cửa sổ chính."""

        def __init__(self, win):
            super().__init__()
            self.win = win

        def che_do_ve(self):
            return (self.lab is not None
                    and (self.win.rb_to.isChecked() or self.win.rb_xoa.isChecked()))

        def che_do_do(self):
            if self.win.rb_do_kc.isChecked():
                return "kc"
            if self.win.rb_do_goc.isChecked():
                return "goc"
            return None

        def brush_mm(self):
            return float(self.win.spin_but.value())

        def bat_dau_net_ve(self, axis, k):
            self.win.bat_dau_net_ve(axis, k)

        def to_tai(self, axis, k, r, c):
            self.win.to_tai(axis, k, r, c)

        def ket_thuc_net_ve(self):
            self.win.ket_thuc_net_ve()

    class NapDicomThread(QtCore.QThread):
        """Đọc DICOM ở luồng nền để giao diện không bị đơ."""
        xong = QtCore.Signal(dict)

        def __init__(self, folder):
            super().__init__()
            self.folder = Path(folder)

        def run(self):
            try:
                img, n_ca, n_lat = khung_xem.quet_va_doc_dicom(self.folder)
                if n_ca > 1:
                    self.xong.emit({"loi": (
                        f"Thư mục này chứa dữ liệu của {n_ca} ca/bệnh nhân khác nhau.\n"
                        "Mỗi lần chỉ nạp MỘT ca — hãy chọn thư mục DICOM của một bệnh nhân.")})
                    return
                if img is None:
                    self.xong.emit({"loi": "Không tìm thấy chuỗi ảnh DICOM nào trong thư mục này."})
                    return
                import SimpleITK as sitk
                import tachrang.core.pipeline as pl
                ct = sitk.GetArrayFromImage(img)
                self.xong.emit({
                    "case": pl.sanitize(self.folder.name),
                    "ct_u8": khung_xem.cua_so_u8(ct),
                    "sp": img.GetSpacing(),
                    "shape": tuple(ct.shape),
                    "matrix": pl.physical_matrix(img),
                    "n_lat": n_lat,
                })
            except Exception as e:
                self.xong.emit({"loi": f"Lỗi đọc DICOM: {e}"})

    class CanScanThread(QtCore.QThread):
        """Căn scan hàm với răng CBCT ở luồng nền (ICP mất vài chục giây đến vài phút)."""
        tien_do = QtCore.Signal(str)
        xong = QtCore.Signal(dict)

        def __init__(self, scan, out, case, ham, xuat_nguoc):
            super().__init__()
            self.args = (Path(scan), Path(out), case, ham, xuat_nguoc)

        def run(self):
            try:
                from tachrang.core import can_scan
                kq = can_scan.can_scan_voi_ca(*self.args, tien_do=self.tien_do.emit)
                kq["mo_ta"] = can_scan.mo_ta_chat_luong(kq["chat_luong"])
                self.xong.emit(kq)
            except Exception as e:
                self.xong.emit({"loi": nhat_ky.giai_thich(e)})

    class XuatHeScanThread(QtCore.QThread):
        """Đưa STL của ca sang hệ tọa độ scan (T^-1) ở luồng nền — xương 80MB mất vài chục giây."""
        tien_do = QtCore.Signal(str)
        xong = QtCore.Signal(dict)

        def __init__(self, stl_dir, T, scan_path, dich, chon):
            super().__init__()
            self.args = (Path(stl_dir), T, scan_path, Path(dich), chon)

        def run(self):
            try:
                from tachrang.core import can_scan
                ra = can_scan.xuat_sang_he_scan(*self.args, tien_do=self.tien_do.emit)
                self.xong.emit({"files": [str(p) for p in ra], "dich": str(self.args[3])})
            except Exception as e:
                self.xong.emit({"loi": nhat_ky.giai_thich(e)})

    class Ghep3ShapeThread(QtCore.QThread):
        """Ghép chân răng CBCT vào Tooth_N.dcm của model set 3Shape (luồng nền, ~1-2 phút/29 răng)."""
        tien_do = QtCore.Signal(str)
        xong = QtCore.Signal(dict)

        def __init__(self, ms_dir, out, case, gap, thu_dir=None, cap_thu_cong=None, dc=None):
            super().__init__()
            self.args = (Path(ms_dir), Path(out), case, gap)
            self.thu_dir = Path(thu_dir) if thu_dir else None
            self.cap = cap_thu_cong
            self.dc = dc

        def run(self):
            try:
                from tachrang.core import chan_rang_3shape as c3
                bc = c3.ghep_model_set(*self.args, thu_dir=self.thu_dir, tien_do=self.tien_do.emit,
                                       cap_thu_cong=self.cap, dc=self.dc,
                                       bo_qua_kiem_bn=self.thu_dir is not None)
                bc["xem_truoc"] = self.thu_dir is not None
                self.xong.emit(bc)
            except Exception as e:
                self.xong.emit({"loi": nhat_ky.giai_thich(e)})

    class DoiChieuThread(QtCore.QThread):
        """Đối chiếu hình học răng 3Shape ↔ CBCT (không ghi) — vài giây."""
        tien_do = QtCore.Signal(str)
        xong = QtCore.Signal(object)

        def __init__(self, ms_dir, out, case):
            super().__init__()
            self.args = (Path(ms_dir), Path(out), case)

        def run(self):
            try:
                from tachrang.core import chan_rang_3shape as c3
                self.xong.emit(c3.doi_chieu(*self.args, tien_do=self.tien_do.emit))
            except Exception as e:
                self.xong.emit({"loi": nhat_ky.giai_thich(e)})

    class ComboKhongLan(QtWidgets.QComboBox):
        """QComboBox trong bảng: lăn chuột để CUỘN BẢNG, không đổi giá trị (trừ khi đang mở/focus)."""

        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)

        def wheelEvent(self, ev):
            if self.hasFocus():
                super().wheelEvent(ev)
            else:
                ev.ignore()

    class MainWindow(QtWidgets.QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("Tách Răng CBCT — Dental Segment Tool")
            self.resize(1320, 820)
            self.proc = None

            splitter = QtWidgets.QSplitter()
            self.setCentralWidget(splitter)

            # ═══ Panel trái: điều khiển (cuộn được khi cửa sổ thấp — không chồng nút) ═══
            left = QtWidgets.QWidget()
            left.setMinimumWidth(1)      # cho phép co ngang theo vùng cuộn (chỉ cuộn dọc)
            cuon_trai = QtWidgets.QScrollArea()
            cuon_trai.setWidget(left)
            cuon_trai.setWidgetResizable(True)
            cuon_trai.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
            cuon_trai.setHorizontalScrollBarPolicy(
                QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            cuon_trai.setMinimumWidth(400)
            cuon_trai.setMaximumWidth(490)
            lv = QtWidgets.QVBoxLayout(left)
            lv.setSpacing(6)
            lv.setContentsMargins(10, 8, 10, 8)

            def tieu_de(text):
                lb = QtWidgets.QLabel(text)
                lb.setStyleSheet("color:#b95d1a; font-weight:700; font-size:10.5pt;"
                                 "padding:2px 0 0 0; background:transparent;")
                lv.addWidget(lb)

            def folder_row(label, line_edit):
                lb = QtWidgets.QLabel(label)
                lb.setStyleSheet("color:#8a7a63;")
                lv.addWidget(lb)
                row = QtWidgets.QHBoxLayout()
                row.addWidget(line_edit)
                btn = QtWidgets.QPushButton("Chọn...")
                row.addWidget(btn)
                lv.addLayout(row)
                return btn

            # Thư mục mặc định: DICOM từng ca; kết quả ra ket_qua (đọc từ config.json / biến môi trường)
            cfg = cau_hinh.doc_cau_hinh()
            default_in = cfg["input_dir"]
            default_out = cfg["output_dir"]
            default_in.mkdir(parents=True, exist_ok=True)
            default_out.mkdir(parents=True, exist_ok=True)
            self._default_in = default_in
            self.in_edit = QtWidgets.QLineEdit("")
            self.in_edit.setPlaceholderText(
                "Chọn thư mục DICOM — hoặc kéo-thả thư mục/file vào cửa sổ...")
            self.out_edit = QtWidgets.QLineEdit(str(default_out))
            tieu_de("①  Dữ liệu")
            # Mở lại dự án cũ chỉ một cú bấm (kiểu Blue Sky Plan / RealGUIDE)
            hang_da = QtWidgets.QHBoxLayout()
            self.btn_mo_du_an = QtWidgets.QPushButton("Mở dự án…")
            self.btn_mo_du_an.setToolTip(
                "Mở file dự án .tachrang — nạp lại DICOM + kết quả + scan của ca chỉ bằng 1 file.\n"
                "File dự án được tự tạo trong <thư mục kết quả>\\du_an\\ mỗi khi nạp một ca.")
            self.btn_mo_du_an.clicked.connect(self._mo_du_an_dialog)
            nut_gd = QtWidgets.QToolButton()
            nut_gd.setText("Gần đây ▾")
            nut_gd.setToolTip("Danh sách dự án đã mở gần đây — bấm để mở lại ngay.")
            nut_gd.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
            self._menu_gan_day = QtWidgets.QMenu(nut_gd)
            self._menu_gan_day.setToolTipsVisible(True)
            self._menu_gan_day.aboutToShow.connect(self._dung_menu_gan_day)
            nut_gd.setMenu(self._menu_gan_day)
            self.btn_luu_du_an = QtWidgets.QPushButton("Lưu dự án")
            self.btn_luu_du_an.setToolTip(
                "Lưu file .tachrang ra nơi tùy chọn (USB, Desktop...) để mở lại/chia sẻ ca này.")
            self.btn_luu_du_an.clicked.connect(self.luu_du_an)
            for w in (self.btn_mo_du_an, nut_gd, self.btn_luu_du_an):
                hang_da.addWidget(w)
            hang_da.addStretch(1)
            lv.addLayout(hang_da)
            folder_row("Thư mục DICOM (mỗi lần 1 bệnh nhân) — chọn xong ảnh hiện ngay:",
                       self.in_edit).clicked.connect(lambda: self._pick(self.in_edit))
            folder_row("Thư mục kết quả (output):", self.out_edit).clicked.connect(
                lambda: self._pick(self.out_edit))

            tieu_de("②  Tách tự động bằng AI")
            box = QtWidgets.QGroupBox("Chế độ tách")
            bl = QtWidgets.QVBoxLayout(box)
            self.rb_combo = QtWidgets.QRadioButton(
                "KẾT HỢP — xương chuẩn + từng răng số FDI (TỐT NHẤT)")
            self.rb_dent = QtWidgets.QRadioButton(
                "DentalSegmentator — 2 hàm + khối răng (nhanh)")
            self.rb_total = QtWidgets.QRadioButton(
                "TotalSeg — từng răng FDI + xoang + ống TK")
            self.rb_uni = QtWidgets.QRadioButton(
                "UniversalLab — răng + răng sữa (máy lạ kém)")
            self.rb_combo.setChecked(True)
            bl.addWidget(self.rb_combo)
            bl.addWidget(self.rb_dent)
            bl.addWidget(self.rb_total)
            bl.addWidget(self.rb_uni)

            dev_row = QtWidgets.QHBoxLayout()
            dev_row.addWidget(QtWidgets.QLabel("Thiết bị:"))
            self.device_box = QtWidgets.QComboBox()
            self.device_box.addItems(["auto", "cuda", "cpu"])
            self.device_box.setCurrentText("auto")
            self.device_box.setToolTip(
                "auto: tự đánh giá GPU/VRAM/RAM của máy và chọn cấu hình tối ưu")
            dev_row.addWidget(self.device_box)
            dev_row.addWidget(QtWidgets.QLabel("Giảm tam giác:"))
            self.decimate_box = QtWidgets.QComboBox()
            self.decimate_box.addItems(["0", "0.3", "0.5", "0.7"])
            dev_row.addWidget(self.decimate_box)
            dev_row.addStretch()
            bl.addLayout(dev_row)

            self.cb_bones = QtWidgets.QCheckBox("Xuất thêm xương (TotalSeg: xương hàm dưới TRỌN VẸN + sọ)")
            self.cb_pulp = QtWidgets.QCheckBox("Xuất thêm tủy từng răng (chỉ TotalSeg)")
            self.cb_seg = QtWidgets.QCheckBox("Input đã là kết quả phân đoạn (bỏ qua AI)")
            bl.addWidget(self.cb_bones)
            bl.addWidget(self.cb_pulp)
            bl.addWidget(self.cb_seg)
            lv.addWidget(box)
            # Tủy răng có ở TotalSeg và Kết hợp; đánh dấu "xuất thêm xương" chỉ có ở TotalSeg
            def _cap_nhat_checkbox(_=False):
                self.cb_pulp.setEnabled(self.rb_total.isChecked() or self.rb_combo.isChecked())
                self.cb_bones.setEnabled(self.rb_total.isChecked())
            self.rb_total.toggled.connect(_cap_nhat_checkbox)
            self.rb_combo.toggled.connect(_cap_nhat_checkbox)
            _cap_nhat_checkbox()

            btn_row = QtWidgets.QHBoxLayout()
            self.run_btn = QtWidgets.QPushButton("▶  Chạy tách răng")
            self.run_btn.setObjectName("run")
            self.stop_btn = QtWidgets.QPushButton("■  Dừng")
            self.stop_btn.setObjectName("stop")
            self.stop_btn.setEnabled(False)
            self.open_btn = QtWidgets.QPushButton("Mở thư mục")
            btn_row.addWidget(self.run_btn, stretch=2)
            btn_row.addWidget(self.stop_btn, stretch=1)
            btn_row.addWidget(self.open_btn, stretch=1)
            lv.addLayout(btn_row)

            self.bar = QtWidgets.QProgressBar()
            self.bar.setRange(0, 1)
            self.bar.setTextVisible(True)
            self.bar.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self.bar.setFormat("")
            lv.addWidget(self.bar)

            case_row = QtWidgets.QHBoxLayout()
            lb_step3 = QtWidgets.QLabel("③  Kiểm tra & chỉnh sửa")
            lb_step3.setStyleSheet("color:#b95d1a; font-weight:700; font-size:10.5pt;"
                                   "background:transparent;")
            lv.addWidget(lb_step3)
            # Mỗi lần mở MỘT ca (theo thư mục DICOM đã chọn) — không cần ô chọn ca
            self._ca_hien = ""
            self.lb_ca = QtWidgets.QLabel("Chưa có kết quả cho ca đang mở")
            self.lb_ca.setStyleSheet("color:#8a7a63;")
            case_row.addWidget(self.lb_ca, stretch=1)
            self.edit_btn = QtWidgets.QPushButton("🖊 Xem && Sửa")
            self.edit_btn.setToolTip(
                "Mở cửa sổ 3 mặt cắt CBCT + 3D:\n"
                "• tích chọn vùng nào muốn xuất\n"
                "• tô thêm / xóa bớt trên lát cắt\n"
                "• xuất lại STL sau khi sửa")
            case_row.addWidget(self.edit_btn)
            lv.addLayout(case_row)

            # ── Sửa trực tiếp ngay tại màn hình chính ──
            gb_sua = QtWidgets.QGroupBox("Các vùng đã tách — sửa trực tiếp trên ảnh")
            gv = QtWidgets.QVBoxLayout(gb_sua)
            gv.setSpacing(4)
            self.ds_vung = QtWidgets.QListWidget()
            self.ds_vung.setMinimumHeight(110)
            self.ds_vung.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding,
                                       QtWidgets.QSizePolicy.Policy.Expanding)
            self.ds_vung.setToolTip("Tích = hiện/ẩn và chọn để xuất — nháy đúp tên để đổi tên")
            gv.addWidget(self.ds_vung, stretch=1)
            row_c = QtWidgets.QHBoxLayout()
            self.btn_all = QtWidgets.QPushButton("Chọn hết")
            self.btn_none = QtWidgets.QPushButton("Bỏ hết")
            self.btn_vungmoi = QtWidgets.QPushButton("＋ Vùng mới")
            self.btn_vungmoi.setToolTip("Thêm một vùng trống rồi dùng 'Tô thêm' để vẽ vùng AI bỏ sót")
            self.btn_gop = QtWidgets.QPushButton("⇄ Gộp vùng...")
            self.btn_gop.setToolTip("Gộp vùng đang chọn vào một vùng khác — nhanh hơn tô tay\n"
                                    "(ví dụ: ghép mảnh chân răng lạc vào đúng răng của nó)")
            row_c.addWidget(self.btn_all)
            row_c.addWidget(self.btn_none)
            row_c.addWidget(self.btn_vungmoi)
            row_c.addWidget(self.btn_gop)
            gv.addLayout(row_c)
            row_b = QtWidgets.QHBoxLayout()
            self.rb_xem = QtWidgets.QRadioButton("Xem")
            self.rb_to = QtWidgets.QRadioButton("Tô thêm")
            self.rb_xoa = QtWidgets.QRadioButton("Xóa bớt")
            self.rb_xem.setChecked(True)
            self.rb_to.setToolTip("Bút CẦU 3D: một nét ăn sâu nhiều lát quanh điểm bôi.\n"
                                  "Tô đè được cả vùng khác (có Hoàn tác Ctrl+Z).\n"
                                  "Bật 'Bút bám chỗ sáng' để không tràn ra mô mềm.")
            self.rb_xoa.setToolTip("Bút CẦU 3D: xóa phần thừa của vùng đang chọn ở nhiều lát liền")
            row_b.addWidget(self.rb_xem)
            row_b.addWidget(self.rb_to)
            row_b.addWidget(self.rb_xoa)
            row_b.addWidget(QtWidgets.QLabel("bút mm:"))
            self.spin_but = QtWidgets.QDoubleSpinBox()
            self.spin_but.setRange(0.3, 15.0)
            self.spin_but.setValue(2.0)
            self.spin_but.setSingleStep(0.5)
            row_b.addWidget(self.spin_but)
            gv.addLayout(row_b)
            self.cb_bam_sang = QtWidgets.QCheckBox("Bút bám chỗ sáng (răng/xương) — tô nhanh không lẹm")
            self.cb_bam_sang.setChecked(True)
            self.cb_bam_sang.setToolTip(
                "Khi tô, chỉ những điểm đủ sáng (theo thanh 'Ngưỡng' dưới khung 3D)\n"
                "mới ăn màu — quét rộng tay vẫn không tràn ra mô mềm/nền đen")
            gv.addWidget(self.cb_bam_sang)
            # Công cụ thông minh (rút gọn từ Segment Editor của 3D Slicer)
            row_t = QtWidgets.QHBoxLayout()
            self.btn_lap = QtWidgets.QPushButton("◫ Lấp ngưỡng")
            self.btn_lap.setToolTip(
                "Thêm vào vùng đang chọn mọi điểm đủ sáng (theo thanh 'Ngưỡng'), chưa có nhãn,\n"
                "liền khối và cách vùng không quá R mm — vá chóp chân răng / mảnh xương AI bỏ sót\n"
                "(tương đương Threshold + Islands trong 3D Slicer)")
            self.btn_min = QtWidgets.QPushButton("◌ Làm mịn")
            self.btn_min.setToolTip(
                "Làm mượt bề mặt vùng đang chọn (Gaussian) — bỏ răng cưa/điểm lẻ sau khi tô tay.\n"
                "Không lấn sang vùng khác.")
            self.btn_moc = QtWidgets.QPushButton("✦ Mọc từ hạt")
            self.btn_moc.setToolTip(
                "Mọi chỗ sáng chưa có nhãn, chạm vào vùng đã có, được gán cho vùng GẦN NHẤT\n"
                "(bản rút gọn của Grow from seeds) — phủ nhanh phần AI còn thiếu cho cả hàm")
            row_t.addWidget(self.btn_lap)
            row_t.addWidget(self.btn_min)
            row_t.addWidget(self.btn_moc)
            gv.addLayout(row_t)
            # Đo khoảng cách / góc trên lát cắt (dùng được ngay khi có CBCT, không cần kết quả)
            row_d = QtWidgets.QHBoxLayout()
            lb_d = QtWidgets.QLabel("Đo:")
            lb_d.setStyleSheet("color:#8a7a63;")
            row_d.addWidget(lb_d)
            self.rb_do_kc = QtWidgets.QRadioButton("Khoảng cách")
            self.rb_do_kc.setToolTip("Bấm 2 điểm trên lát cắt -> hiện mm")
            self.rb_do_goc = QtWidgets.QRadioButton("Góc")
            self.rb_do_goc.setToolTip("Bấm 3 điểm (điểm giữa là đỉnh góc) -> hiện độ")
            self.btn_xoa_do = QtWidgets.QPushButton("Xóa số đo")
            self.lb_do = QtWidgets.QLabel("")
            self.lb_do.setStyleSheet("color:#0b7285; font-weight:600;")
            row_d.addWidget(self.rb_do_kc)
            row_d.addWidget(self.rb_do_goc)
            row_d.addWidget(self.btn_xoa_do)
            row_d.addWidget(self.lb_do, stretch=1)
            gv.addLayout(row_d)
            row_s = QtWidgets.QHBoxLayout()
            self.btn_undo = QtWidgets.QPushButton("↩ Hoàn tác")
            self.btn_undo.setToolTip("Lùi lại nét tô/xóa vừa rồi (Ctrl+Z)")
            self.btn_luu = QtWidgets.QPushButton("💾 Lưu sửa")
            self.btn_xuat = QtWidgets.QPushButton("⬇ Xuất STL vùng đã tích")
            row_s.addWidget(self.btn_undo)
            row_s.addWidget(self.btn_luu)
            row_s.addWidget(self.btn_xuat)
            gv.addLayout(row_s)
            # Bản LÀM DỞ: lưu riêng (không đè kết quả gốc) để lần sau mở lại tiếp
            row_n = QtWidgets.QHBoxLayout()
            self.btn_nhap = QtWidgets.QPushButton("📝 Lưu bản làm dở")
            self.btn_nhap.setToolTip(
                "Lưu tình trạng đang sửa vào file NHÁP riêng (không đè kết quả gốc).\n"
                "Tự động lưu nháp mỗi 3 phút khi có thay đổi và khi đóng chương trình.")
            self.btn_khoi_phuc = QtWidgets.QPushButton("↻ Khôi phục bản làm dở")
            self.btn_khoi_phuc.setToolTip(
                "Mở lại bản nháp đã lưu của ca này để làm tiếp.\n"
                "Chương trình KHÔNG bao giờ tự nạp nháp — chỉ nạp khi bấm nút này.")
            self.btn_khoi_phuc.setEnabled(False)
            row_n.addWidget(self.btn_nhap)
            row_n.addWidget(self.btn_khoi_phuc)
            self.btn_mo_file = QtWidgets.QPushButton("📂 Mở file…")
            self.btn_mo_file.setToolTip(
                "Nạp một file nhãn .nii.gz đã lưu trước (kết quả gốc, bản làm dở\n"
                "hay bản sao đã sửa) để chỉnh tiếp trên ca đang mở")
            row_n.addWidget(self.btn_mo_file)
            gv.addLayout(row_n)
            self.lb_nhap = QtWidgets.QLabel("")
            self.lb_nhap.setStyleSheet("color:#8a7a63; font-size:9pt;")
            gv.addWidget(self.lb_nhap)
            lv.addWidget(gb_sua, stretch=2)

            # ── Tab "Căn Scan ⇄ CBCT": tính phép đặt scan ↔ răng CBCT, riêng từng hàm ──
            self.tab_scan = QtWidgets.QWidget()
            gs = QtWidgets.QVBoxLayout(self.tab_scan)
            gs.setSpacing(6)
            self.lb_ca_scan = QtWidgets.QLabel("")
            self.lb_ca_scan.setWordWrap(True)
            gs.addWidget(self.lb_ca_scan)
            lb_hd = QtWidgets.QLabel(
                "Bước này tính <b>phép đặt (ma trận)</b> giữa file scan và răng tách từ CBCT, "
                "<b>riêng từng hàm</b>; scan hiện chồng lên răng CBCT trong khung 3D kèm sai số để kiểm tra. "
                "<b>Chọn ĐÚNG file scan đã import vào 3Shape</b> (không dùng file <i>occlusion</i>). "
                "Khi <b>Ghép</b> ở tab 🧩 3Shape, chân răng CBCT tự động được đưa <b>về hệ tọa độ scan</b> "
                "bằng phép đặt ngược — file scan và răng trong 3Shape không bị di chuyển; "
                "chỉ cần căn hàm nào sẽ ghép hàm đó.")
            lb_hd.setWordWrap(True)
            lb_hd.setStyleSheet("color:#8a7a63; font-size:9pt;")
            gs.addWidget(lb_hd)

            def khu_ham(dau, ten, goi_y_file):
                g = QtWidgets.QGroupBox(f"{dau}  {ten}")
                va = QtWidgets.QVBoxLayout(g)
                va.setSpacing(4)
                lb_tt = QtWidgets.QLabel()
                lb_tt.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                lb_tt.setMinimumHeight(26)
                va.addWidget(lb_tt)
                row = QtWidgets.QHBoxLayout()
                lb_f = QtWidgets.QLabel("File scan:")
                lb_f.setStyleSheet("color:#8a7a63;")
                row.addWidget(lb_f)
                ed = QtWidgets.QLineEdit("")
                ed.setPlaceholderText(goi_y_file)
                bp = QtWidgets.QPushButton("Chọn...")
                row.addWidget(ed, stretch=1)
                row.addWidget(bp)
                va.addLayout(row)
                bc = QtWidgets.QPushButton(f"⇄  Căn {ten.lower()} với răng CBCT")
                bc.setObjectName("run")
                bc.setToolTip(
                    "Tự tìm phép xoay/tịnh tiến khớp thân răng trên scan với răng CBCT\n"
                    "(FPFH+RANSAC rồi ICP bền, bỏ qua nướu/nhiễu). Xong hiện scan bán trong suốt\n"
                    "chồng lên răng CBCT trong khung 3D kèm sai số mm để kiểm tra bằng mắt.")
                va.addWidget(bc)
                return g, ed, bp, bc, lb_tt

            (g_tren, self.scan_edit_tren, self.btn_pick_tren,
             self.btn_can_tren, self.lb_ham_tren) = khu_ham(
                "▲", "Hàm trên", "File scan hàm trên (tên thường có 'maxillary'/'upper')...")
            (g_duoi, self.scan_edit_duoi, self.btn_pick_duoi,
             self.btn_can_duoi, self.lb_ham_duoi) = khu_ham(
                "▼", "Hàm dưới", "File scan hàm dưới (tên thường có 'mandibular'/'lower')...")
            gs.addWidget(g_tren)
            gs.addWidget(g_duoi)
            # Danh sách scan của ca (chưa căn / đã căn): tích = hiện trong 3D
            lb_ds = QtWidgets.QLabel("Scan của ca này (tích = hiện trong 3D; CAM = chưa căn, XANH = đã căn):")
            lb_ds.setStyleSheet("color:#8a7a63; font-size:9pt;")
            gs.addWidget(lb_ds)
            self.ds_scan = QtWidgets.QListWidget()
            self.ds_scan.setMinimumHeight(56)
            self.ds_scan.setMaximumHeight(110)
            self.ds_scan.setToolTip("Các scan của ca này. Tích = hiện/ẩn trong 3D; "
                                    "nháy đúp = xem chi tiết phép căn")
            gs.addWidget(self.ds_scan)
            row_sc5 = QtWidgets.QHBoxLayout()
            self.btn_scan_chitiet = QtWidgets.QPushButton("ℹ Chi tiết")
            self.btn_scan_thumuc = QtWidgets.QPushButton("📂 Thư mục")
            self.btn_scan_bo = QtWidgets.QPushButton("✕ Bỏ")
            self.btn_scan_bo.setToolTip("Bỏ scan này khỏi khung 3D (file trên đĩa giữ nguyên)")
            for b in (self.btn_scan_chitiet, self.btn_scan_thumuc, self.btn_scan_bo):
                row_sc5.addWidget(b)
            gs.addLayout(row_sc5)
            # Nâng cao (ít dùng): xuất ngược sang hệ scan
            nang_cao = QtWidgets.QGroupBox("Nâng cao — xuất sang hệ tọa độ scan (không cần cho 3Shape)")
            nang_cao.setCheckable(True)
            nang_cao.setChecked(False)
            nang_cao.setStyleSheet("QGroupBox{font-size:9pt; color:#8a7a63;}")
            self._nc_scan = QtWidgets.QWidget()
            nc = QtWidgets.QVBoxLayout(self._nc_scan)
            nc.setContentsMargins(0, 0, 0, 0)
            nc.setSpacing(3)
            self.cb_scan_nguoc = QtWidgets.QCheckBox("Khi căn, xuất thêm STL CBCT sang hệ tọa độ scan")
            self.cb_scan_nguoc.setToolTip(
                "Mặc định: scan được đưa VỀ hệ tọa độ CBCT (cùng hệ các STL đã tách).\n"
                "Tích: xuất thêm bản sao toàn bộ STL của ca sang hệ của scan\n"
                "(thư mục he-toa-do-scan) để mở trong phần mềm CAD cùng file scan gốc.")
            nc.addWidget(self.cb_scan_nguoc)
            row_sc4 = QtWidgets.QHBoxLayout()
            self.btn_scan_xuat = QtWidgets.QPushButton("⬇ Xuất scan…")
            self.btn_scan_xuat.setToolTip("Lưu bản scan ĐÃ CĂN (hệ tọa độ CBCT) ra nơi khác")
            self.btn_scan_nguoc = QtWidgets.QPushButton("⇄ STL răng → hệ scan…")
            self.btn_scan_nguoc.setToolTip(
                "Dùng ma trận đã căn của scan đang chọn để đưa MỌI STL của ca (răng, xương, xoang...)\n"
                "sang hệ tọa độ của file scan GỐC — mở chung trong exocad/3Shape/Meshmixer\n"
                "cùng scan gốc là khớp ngay. Không chạy lại căn, chứ vài chục giây.")
            for b in (self.btn_scan_xuat, self.btn_scan_nguoc):
                row_sc4.addWidget(b)
            nc.addLayout(row_sc4)
            ncl = QtWidgets.QVBoxLayout(nang_cao)
            ncl.setContentsMargins(4, 2, 4, 4)
            ncl.addWidget(self._nc_scan)
            self._nc_scan.setVisible(False)
            nang_cao.toggled.connect(self._nc_scan.setVisible)
            gs.addWidget(nang_cao)
            self.lb_scan = QtWidgets.QLabel("")
            self.lb_scan.setWordWrap(True)
            self.lb_scan.setTextInteractionFlags(
                QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
            self.lb_scan.setStyleSheet("color:#8a7a63; font-size:9pt;")
            gs.addWidget(self.lb_scan)
            gs.addStretch(1)
            self._scan_items = {}      # đường dẫn file -> {"actor", "item", "da_can", "info"}
            self._scan_thread = None
            self._3s_thread = None
            self._cap_nhat_trang_thai_ham()
            self.tab_3shape = self._tao_tab_3shape()   # module riêng: tab "3Shape OrthoAnalyzer"

            self.cb_ct3d = QtWidgets.QCheckBox("Hiện CBCT mờ trong khung 3D")
            self.cb_ct3d.setChecked(True)
            self.cb_ct3d.toggled.connect(self._bat_tat_ct3d)
            lv.addWidget(self.cb_ct3d)

            lv.addWidget(QtWidgets.QLabel("Tiến trình:"))
            self.log = QtWidgets.QPlainTextEdit()
            self.log.setReadOnly(True)
            self.log.setMinimumHeight(70)
            self.log.setStyleSheet(
                "background:#101418; color:#d8dee9; font-family:Consolas; font-size:9pt;")
            lv.addWidget(self.log, stretch=1)

            # ═══ Panel phải: 3 lát cắt CBCT + khung 3D (kéo viền để đổi cỡ) ═══
            right = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
            right.setHandleWidth(6)
            hang_tren = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
            hang_duoi = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
            for s in (hang_tren, hang_duoi):
                s.setHandleWidth(6)
                s.setChildrenCollapsible(False)
            right.setChildrenCollapsible(False)

            self.nguon = NguonSua(self)
            self.nguon.khi_doi_lat = self._dong_bo_truot
            self.nguon.khi_bam_nhan = self._bam_nhan   # bấm răng trên ảnh -> chọn dòng
            self.nguon.khi_do_xong = self._do_xong     # xong 1 số đo -> hiện giá trị
            self.canvases = []
            self.sliders = []
            self._o_lat = []            # 3 ô lát cắt (ẩn khi sang tab 3Shape)
            self.hang_tren, self.hang_duoi, self.chia_phai = hang_tren, hang_duoi, right
            for axis, chua in ((0, hang_tren), (1, hang_tren), (2, hang_duoi)):
                cell = QtWidgets.QWidget()
                self._o_lat.append(cell)
                cl = QtWidgets.QVBoxLayout(cell)
                cl.setContentsMargins(0, 0, 0, 0)
                cl.setSpacing(2)
                cv = khung_xem.KhungLat(self.nguon, axis)
                sl = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
                sl.setRange(0, 0)
                sl.valueChanged.connect(lambda v, cv=cv: cv.set_k(v))
                cl.addWidget(cv, stretch=1)
                cl.addWidget(sl)
                chua.addWidget(cell)
                self.canvases.append(cv)
                self.sliders.append(sl)
            self.nguon.canvases = self.canvases  # để xoay lát cập nhật cả 3 khung

            cell3d = QtWidgets.QWidget()
            c3 = QtWidgets.QVBoxLayout(cell3d)
            c3.setContentsMargins(0, 0, 0, 0)
            c3.setSpacing(2)
            self.vtk_widget = QVTKRenderWindowInteractor(cell3d)
            self.renderer = vtk.vtkRenderer()
            self.renderer.GradientBackgroundOn()
            self.renderer.SetBackground(0.09, 0.11, 0.14)
            self.renderer.SetBackground2(0.25, 0.28, 0.32)
            self.vtk_widget.GetRenderWindow().AddRenderer(self.renderer)
            iren = self.vtk_widget.GetRenderWindow().GetInteractor()
            iren.SetInteractorStyle(vtk.vtkInteractorStyleTrackballCamera())
            c3.addWidget(self.vtk_widget, stretch=1)

            # Thanh chỉnh kiểu hiển thị khối CBCT 3D
            self.thanh_3d = QtWidgets.QWidget()
            row3d = QtWidgets.QHBoxLayout(self.thanh_3d)
            row3d.setContentsMargins(0, 0, 0, 0)
            row3d.setSpacing(6)
            self.kieu_3d = QtWidgets.QComboBox()
            self.kieu_3d.addItems(["Xương + răng", "Chỉ răng (đặc)", "Cả da/mô mềm"])
            self.kieu_3d.setToolTip("Kiểu hiển thị có sẵn cho khối CBCT 3D")
            row3d.addWidget(self.kieu_3d)
            row3d.addWidget(QtWidgets.QLabel("Ngưỡng:"))
            self.sl_nguong = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
            self.sl_nguong.setRange(30, 235)
            self.sl_nguong.setValue(120)
            self.sl_nguong.setToolTip(
                "Kéo PHẢI: chỉ còn răng/xương đặc — kéo TRÁI: thấy cả da/mô mềm")
            row3d.addWidget(self.sl_nguong, stretch=1)
            row3d.addWidget(QtWidgets.QLabel("Đậm:"))
            self.sl_dam = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
            self.sl_dam.setRange(4, 95)
            self.sl_dam.setValue(28)
            self.sl_dam.setToolTip("Độ đậm/đặc của khối CBCT (kéo phải = đặc rõ)")
            row3d.addWidget(self.sl_dam, stretch=1)
            c3.addWidget(self.thanh_3d)
            hang_duoi.addWidget(cell3d)
            right.addWidget(hang_tren)
            right.addWidget(hang_duoi)
            right.setSizes([500, 500])
            hang_tren.setSizes([500, 500])
            hang_duoi.setSizes([500, 500])

            # Thanh SÁNG / TƯƠNG PHẢN cho 3 lát cắt (kéo chuột PHẢI trên ảnh cũng đổi)
            khung_phai = QtWidgets.QWidget()
            kp = QtWidgets.QVBoxLayout(khung_phai)
            kp.setContentsMargins(0, 0, 0, 0)
            kp.setSpacing(3)
            self.thanh_cua_so = QtWidgets.QWidget()
            row_ws = QtWidgets.QHBoxLayout(self.thanh_cua_so)
            row_ws.setContentsMargins(0, 0, 0, 0)
            row_ws.setSpacing(6)
            lb_ws = QtWidgets.QLabel("Ảnh lát cắt:")
            lb_ws.setStyleSheet("color:#8a7a63;")
            row_ws.addWidget(lb_ws)
            self.cb_cua_so = QtWidgets.QComboBox()
            self.cb_cua_so.addItems(["Mặc định", "Răng (men/ngà rõ)", "Xương",
                                     "Mô mềm", "Tùy chỉnh"])
            self.cb_cua_so.setToolTip("Cửa sổ hiển thị có sẵn cho lát cắt CBCT")
            row_ws.addWidget(self.cb_cua_so)
            row_ws.addWidget(QtWidgets.QLabel("Sáng:"))
            self.sl_sang = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
            self.sl_sang.setRange(-50, 305)
            self.sl_sang.setValue(255 - 128)
            self.sl_sang.setToolTip("Kéo phải = ảnh sáng hơn")
            row_ws.addWidget(self.sl_sang, stretch=1)
            row_ws.addWidget(QtWidgets.QLabel("Tương phản:"))
            self.sl_tphan = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
            self.sl_tphan.setRange(8, 600)
            self.sl_tphan.setValue(608 - 256)
            self.sl_tphan.setToolTip("Kéo phải = tương phản mạnh hơn (cửa sổ hẹp)")
            row_ws.addWidget(self.sl_tphan, stretch=1)
            self.btn_ws_reset = QtWidgets.QPushButton("↺")
            self.btn_ws_reset.setFixedWidth(30)
            self.btn_ws_reset.setToolTip("Về mặc định")
            row_ws.addWidget(self.btn_ws_reset)
            kp.addWidget(self.thanh_cua_so)
            kp.addWidget(right, stretch=1)
            self._co_phai_luu = None   # kích cỡ splitter phải trước khi sang chế độ chỉ 3D
            self.cb_cua_so.currentIndexChanged.connect(self._chon_cua_so)
            self.sl_sang.valueChanged.connect(self._keo_cua_so)
            self.sl_tphan.valueChanged.connect(self._keo_cua_so)
            self.btn_ws_reset.clicked.connect(lambda: self.cb_cua_so.setCurrentIndex(0))
            self.nguon.khi_doi_cua_so = self._dong_bo_cua_so

            axes = vtk.vtkAxesActor()
            self.marker = vtk.vtkOrientationMarkerWidget()
            self.marker.SetOrientationMarker(axes)
            self.marker.SetInteractor(iren)
            self.marker.SetViewport(0.0, 0.0, 0.15, 0.15)
            self.marker.EnabledOn()
            self.marker.InteractiveOff()

            self.hint = vtk.vtkTextActor()
            self.hint.GetTextProperty().SetFontSize(15)
            self.hint.GetTextProperty().SetColor(0.85, 0.85, 0.85)
            self.hint.SetPosition(12, 10)
            self.hint.SetInput("Chon thu muc DICOM cua MOT benh nhan de xem CBCT tai day")
            self.renderer.AddActor2D(self.hint)

            self.volume_actor = None
            self._ct_case = None
            self._da_nap = None
            self._dang_nap = None
            self._loader = None
            self._matrix = None
            self.lab = None                # bản đồ nhãn đang sửa (numpy int16)
            self.names = {}                # id -> tên vùng
            self.undo_stack = []
            self._net = None               # nét vẽ đang quét (list bbox+patch)
            self._nhan_sua = None          # nhãn đang tô (để cập nhật 3D khi nhả chuột)
            self._bo_qua_nhay = False      # chặn nhảy lát khi chọn dòng do bấm ảnh
            self.settings = QtCore.QSettings("DentalSegment", "TachRang")
            nho_in = str(self.settings.value("in_dir", ""))
            if nho_in and Path(nho_in).is_dir():
                self.in_edit.setPlaceholderText(f"Lần trước: {nho_in}")
            self._lm_img = None
            self._case_edit = None
            self._sua_dirty = False
            self._stl_actors = {}          # tên file stl (thường) -> actor
            self._actors_nhan = {}         # id nhãn -> actor

            # ── Panel trái: TAB TÍNH NĂNG — đăng ký tập trung tại _tab_muc (thêm tab mới
            #    = thêm 1 dòng); nút ☰ góc phải bật/tắt từng tab (nhớ QSettings "tabs_an") ──
            self.tabs_trai = QtWidgets.QTabWidget()
            self.tabs_trai.setMinimumWidth(400)
            self.tabs_trai.setMaximumWidth(490)
            self.tabs_trai.setDocumentMode(True)
            self.tabs_trai.setUsesScrollButtons(True)
            cuon_trai.setMinimumWidth(1)
            cuon_trai.setMaximumWidth(16777215)
            self._cuon_scan = QtWidgets.QScrollArea()
            self._cuon_scan.setWidget(self.tab_scan)
            self._cuon_scan.setWidgetResizable(True)
            self._cuon_scan.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
            self._tab_muc = [   # (id, widget, tên tab, mô tả, luôn hiện?)
                ("tach", cuon_trai, "🦷 Tách răng",
                 "Tách răng & xương từ ảnh CBCT (bước ① dữ liệu, ② chạy AI, ③ chỉnh sửa)", True),
                ("scan", self._cuon_scan, "⇄ Căn scan",
                 "Căn scan hàm với răng CBCT — tính phép đặt dùng khi ghép vào 3Shape", False),
                ("3shape", self.tab_3shape, "🧩 3Shape",
                 "Ghép chân răng thật vào model set 3Shape OrthoAnalyzer", False),
            ]
            for _tid, wd, ten, mota, _khoa in self._tab_muc:
                self.tabs_trai.setTabToolTip(self.tabs_trai.addTab(wd, ten), mota)
            nut_tab = QtWidgets.QToolButton()
            nut_tab.setObjectName("nut_tab_menu")
            nut_tab.setText("☰")
            nut_tab.setToolTip("Bật/tắt các tính năng (ẩn/hiện tab)")
            nut_tab.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
            menu_tab = QtWidgets.QMenu(nut_tab)
            menu_tab.setToolTipsVisible(True)
            an_luu = self._tabs_an()
            for tid, _wd, ten, mota, khoa in self._tab_muc:
                ac = menu_tab.addAction(ten)
                ac.setToolTip(mota)
                ac.setCheckable(True)
                ac.setChecked(tid not in an_luu)
                ac.setEnabled(not khoa)          # tab chính không tắt được
                ac.toggled.connect(lambda hien, t=tid: self._dat_tab_hien(t, hien))
            nut_tab.setMenu(menu_tab)
            self.tabs_trai.setCornerWidget(nut_tab, QtCore.Qt.Corner.TopRightCorner)
            for tid in an_luu:
                self._dat_tab_hien(tid, False, luu=False)
            self.tabs_trai.currentChanged.connect(self._doi_tab_trai)
            splitter.addWidget(self.tabs_trai)
            splitter.addWidget(khung_phai)
            splitter.setSizes([410, 910])
            self.statusBar().showMessage("Sẵn sàng")

            # Kết nối
            self.run_btn.clicked.connect(self.on_run)
            self.stop_btn.clicked.connect(self.on_stop)
            self.open_btn.clicked.connect(self.on_open_out)
            self.edit_btn.clicked.connect(self.on_edit)
            self.btn_nhap.clicked.connect(lambda: self.luu_nhap(tu_dong=False))
            self.btn_khoi_phuc.clicked.connect(lambda: self.khoi_phuc_nhap(hoi=True))
            self.btn_mo_file.clicked.connect(self.mo_file_nhan)
            self.btn_pick_tren.clicked.connect(lambda: self._chon_scan("tren"))
            self.btn_pick_duoi.clicked.connect(lambda: self._chon_scan("duoi"))
            self.btn_can_tren.clicked.connect(lambda: self.can_scan("tren"))
            self.btn_can_duoi.clicked.connect(lambda: self.can_scan("duoi"))
            self.ds_scan.itemChanged.connect(self._scan_item_doi)
            self.ds_scan.itemDoubleClicked.connect(lambda _it: self._scan_chi_tiet())
            self.btn_scan_xuat.clicked.connect(self._scan_xuat)
            self.btn_scan_nguoc.clicked.connect(self._scan_xuat_nguoc)
            self.btn_scan_chitiet.clicked.connect(self._scan_chi_tiet)
            self.btn_scan_thumuc.clicked.connect(self._scan_mo_thu_muc)
            self.btn_scan_bo.clicked.connect(self._scan_bo)
            self._timer_nhap = QtCore.QTimer(self)
            self._timer_nhap.setInterval(3 * 60 * 1000)
            self._timer_nhap.timeout.connect(lambda: self.luu_nhap(tu_dong=True))
            self._timer_nhap.start()
            self.in_edit.editingFinished.connect(self._in_edit_xong)
            self.kieu_3d.currentIndexChanged.connect(self._ap_kieu_3d)
            self.sl_nguong.valueChanged.connect(self._chinh_volume)
            self.sl_dam.valueChanged.connect(self._chinh_volume)
            self.btn_all.clicked.connect(lambda: self._tick_het(True))
            self.btn_none.clicked.connect(lambda: self._tick_het(False))
            self.btn_vungmoi.clicked.connect(self._vung_moi)
            self.btn_gop.clicked.connect(self._gop_vung)
            self.btn_lap.clicked.connect(self._lap_nguong)
            self.btn_min.clicked.connect(self._lam_min)
            self.btn_moc.clicked.connect(self._moc_tu_hat)
            self.btn_xoa_do.clicked.connect(self._xoa_do)
            self.btn_undo.clicked.connect(self.hoan_tac)
            self.ds_vung.currentItemChanged.connect(self._nhay_den_vung)
            self.btn_luu.clicked.connect(self.luu_nhan)
            self.btn_xuat.clicked.connect(self.xuat_stl_sua)
            self.ds_vung.itemChanged.connect(self._doi_item)
            QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Z"), self, self.hoan_tac)

            self.vtk_widget.GetRenderWindow().Render()
            iren.Initialize()
            QtCore.QTimer.singleShot(200, self.detect_gpu)
            # Kéo-thả thông minh: thả thư mục DICOM / file .tachrang / .nii.gz / scan vào cửa sổ
            self.setAcceptDrops(True)
            self._scan_cho = None          # scan chờ điền lại sau khi mở dự án
            ds_gd = self._ds_gan_day()
            if ds_gd:
                QtCore.QTimer.singleShot(400, lambda: self.statusBar().showMessage(
                    f"Có {len(ds_gd)} dự án gần đây — bấm 'Gần đây ▾' để mở lại chỉ một cú bấm",
                    10000))

        # ── Tiện ích ──────────────────────────────────────────────────────
        def _pick(self, edit):
            start = edit.text().strip() or str(self._default_in)
            d = QtWidgets.QFileDialog.getExistingDirectory(self, "Chọn thư mục", start)
            if d:
                edit.setText(d)
                if edit is self.out_edit:
                    self.settings.setValue("out_dir", d)
                    self.refresh_cases(auto_render=True)
                elif not self.cb_seg.isChecked():
                    self.settings.setValue("in_dir", d)
                    self.nap_dicom(d)

        def log_write(self, text):
            self.log.moveCursor(self.log.textCursor().MoveOperation.End)
            self.log.insertPlainText(text.replace("\r", "\n"))
            self.log.moveCursor(self.log.textCursor().MoveOperation.End)

        def detect_gpu(self):
            self._gpu_proc = QtCore.QProcess(self)
            self._gpu_proc.finished.connect(self._gpu_done)
            if getattr(sys, "frozen", False):   # exe đóng gói không hiểu "-c"
                self._gpu_proc.start(sys.executable, ["--gpu-probe"])
            else:
                self._gpu_proc.start(sys.executable, ["-c",
                    "import torch; print(int(torch.cuda.is_available()))"])

        @staticmethod
        def _co_card_nvidia():
            """Máy có card NVIDIA cắm trên khe PCI không (kể cả khi CHƯA cài driver)?
            Đọc cây liệt kê phần cứng trong registry — không cần tiến trình con."""
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                    r"SYSTEM\CurrentControlSet\Enum\PCI") as k:
                    for i in range(winreg.QueryInfoKey(k)[0]):
                        if winreg.EnumKey(k, i).upper().startswith("VEN_10DE"):  # 10DE = NVIDIA
                            return True
            except OSError:
                pass
            return False

        def _gpu_done(self):
            out = bytes(self._gpu_proc.readAllStandardOutput()).decode(errors="replace")
            has_gpu = out.strip().endswith("1")
            # Giữ "auto" — pipeline sẽ tự chọn; chỉ thông báo cho người dùng biết
            if has_gpu:
                self.log_write("[GPU] Phát hiện GPU CUDA — chế độ auto sẽ dùng GPU\n")
            elif self._co_card_nvidia():
                self.log_write(
                    "[GPU] Máy CÓ card NVIDIA nhưng CHƯA cài driver (hoặc driver quá cũ) — tạm chạy CPU, chậm hơn nhiều.\n"
                    "      → Cài driver mới nhất tại nvidia.com/drivers (hoặc GeForce Experience), "
                    "xong mở lại chương trình là tự chuyển sang GPU — KHÔNG cần cài lại app.\n")
            else:
                self.log_write("[GPU] Không có GPU CUDA — chế độ auto sẽ dùng CPU\n")

        # ── Nạp & hiển thị CBCT ngay khi chọn thư mục ────────────────────
        def _dong_bo_truot(self, axis, k):
            sl = self.sliders[axis]
            sl.blockSignals(True)
            sl.setValue(int(k))
            sl.blockSignals(False)

        def _in_edit_xong(self):
            p = self.in_edit.text().strip()
            if p and Path(p).is_dir() and not self.cb_seg.isChecked():
                self.nap_dicom(p)

        def nap_dicom(self, folder):
            folder = str(Path(folder))
            if folder in (self._da_nap, self._dang_nap):
                return
            if self._loader is not None and self._loader.isRunning():
                return
            self._dang_nap = folder
            self.statusBar().showMessage("Đang nạp DICOM...")
            self.log_write(f"[Nạp DICOM] {folder} ...\n")
            self._loader = NapDicomThread(folder)
            self._loader.xong.connect(self._nap_xong)
            self._loader.start()

        def _nap_xong(self, d):
            folder = self._dang_nap
            self._dang_nap = None
            if "loi" in d:
                self.statusBar().showMessage("Nạp DICOM thất bại")
                self.log_write("[Nạp DICOM] " + d["loi"] + "\n")
                QtWidgets.QMessageBox.warning(self, "Không nạp được DICOM", d["loi"])
                return
            self._da_nap = folder
            ca_cu = self._ct_case
            self._ct_case = d["case"]
            self._matrix = d["matrix"]
            # DICOM của CA KHÁC -> scan (thô lẫn đã căn) của ca cũ không còn ý nghĩa: bỏ hết,
            # xóa ô đường dẫn; scan đã căn của ca mới sẽ được render_case nạp lại từ thư mục kết quả
            if ca_cu and ca_cu != d["case"]:
                self._scan_xoa_het()
                self.scan_edit_tren.setText("")
                self.scan_edit_duoi.setText("")
                self.lb_scan.setText("")
            # Mở từ file dự án: điền lại đường dẫn scan đã ghi trong dự án
            cho = getattr(self, "_scan_cho", None)
            self._scan_cho = None
            if cho and cho.get("case") == d["case"]:
                if cho.get("tren"):
                    self.scan_edit_tren.setText(cho["tren"])
                if cho.get("duoi"):
                    self.scan_edit_duoi.setText(cho["duoi"])
            # DICOM mới -> bỏ bản đồ nhãn của ca cũ (tránh lệch kích thước)
            self.lab = None
            self._case_edit = None
            self.undo_stack = []
            self.ds_vung.blockSignals(True)
            self.ds_vung.clear()
            self.ds_vung.blockSignals(False)
            n = self.nguon
            n.lab = None
            n.ct_u8 = d["ct_u8"]
            n.sp = d["sp"]
            n.shape = d["shape"]
            n.epoch += 1
            for cv, sl in zip(self.canvases, self.sliders):
                sl.blockSignals(True)
                sl.setRange(0, n.shape[cv.axis] - 1)
                cv.dat_lai()
                sl.setValue(cv.k)
                sl.blockSignals(False)
            # khối 3D CBCT trong khung 3D
            self.renderer.RemoveAllViewProps()
            self.hint.SetInput(f"CBCT: {d['case']}  —  lan chuot tren anh = doi lat, "
                               "Ctrl+lan = phong to")
            self.renderer.AddActor2D(self.hint)
            self.volume_actor = khung_xem.tao_volume_ct(
                n.ct_u8, d["matrix"], nguong=float(self.sl_nguong.value()),
                do_dam=self.sl_dam.value() / 100.0)
            self.renderer.AddVolume(self.volume_actor)
            self.volume_actor.SetVisibility(self.cb_ct3d.isChecked())
            if self._scan_items:                       # giữ các scan đang nạp
                for d in self._scan_items.values():
                    self.renderer.AddActor(d["actor"])
                self._scan_cap_nhat_lat()              # CT mới -> viền scan tính lại
            self.renderer.ResetCamera()
            self.vtk_widget.GetRenderWindow().Render()
            z, y, x = n.shape
            self.log_write(f"[Nạp DICOM] OK: {d['case']} — {d['n_lat']} lát DICOM, "
                           f"khối {x}×{y}×{z}\n")
            self.statusBar().showMessage(
                f"Đã nạp CBCT: {d['case']} ({x}×{y}×{z}) — sẵn sàng chạy tách")
            # Ca này đã tách trước đó? -> mở luôn kết quả để kiểm tra/sửa tiếp
            self._ca_hien = ""
            self.refresh_cases(auto_render=True)
            self._luu_du_an_tu_dong()   # cập nhật file .tachrang để 'Gần đây' mở lại 1 cú bấm

        def _bat_tat_ct3d(self, on):
            if self.volume_actor is not None:
                self.volume_actor.SetVisibility(bool(on))
                self.vtk_widget.GetRenderWindow().Render()

        # ── Dự án (.tachrang) + Gần đây + kéo-thả thông minh ────────────
        # Kiểu Blue Sky Plan / RealGUIDE: 1 file dự án nhẹ (JSON) trỏ tới DICOM,
        # thư mục kết quả và scan — mở lại toàn bộ phiên làm việc bằng 1 cú bấm.
        # Dữ liệu nặng vẫn nằm trong thư mục kết quả; file dự án chỉ là "con trỏ".
        def _du_an_data(self):
            return {
                "phan_mem": "TachRang", "phien_ban": 1,
                "case": self._ct_case or self._case_edit or "",
                "dicom_dir": self._da_nap or self.in_edit.text().strip(),
                "out_dir": self.out_edit.text().strip(),
                "scan_tren": self.scan_edit_tren.text().strip(),
                "scan_duoi": self.scan_edit_duoi.text().strip(),
                "luu_luc": time.strftime("%Y-%m-%d %H:%M:%S"),
            }

        def _duong_du_an(self, case):
            return Path(self.out_edit.text().strip() or ".") / "du_an" / f"{case}.tachrang"

        def _luu_du_an_tu_dong(self):
            """Ghi/cập nhật file dự án trong <kết quả>/du_an/ — âm thầm, không hỏi."""
            d = self._du_an_data()
            if not d["case"] or not d["out_dir"]:
                return
            try:
                f = self._duong_du_an(d["case"])
                f.parent.mkdir(parents=True, exist_ok=True)
                tam = f.with_name(f.name + ".tam")
                tam.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
                os.replace(tam, f)
                self._them_gan_day(str(f))
            except Exception:
                pass                      # dự án chỉ là tiện ích — không được làm phiền

        def luu_du_an(self):
            """Lưu file .tachrang ra nơi tùy chọn để chia sẻ/mở lại ca bằng 1 file."""
            d = self._du_an_data()
            if not d["case"]:
                QtWidgets.QMessageBox.information(
                    self, "Chưa có ca",
                    "Hãy nạp DICOM hoặc mở một ca có kết quả trước khi lưu dự án.")
                return
            self._luu_du_an_tu_dong()
            duong, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Lưu file dự án", str(self._duong_du_an(d["case"])),
                "Dự án TachRang (*.tachrang)")
            if not duong:
                return
            try:
                Path(duong).write_text(json.dumps(d, ensure_ascii=False, indent=1),
                                       encoding="utf-8")
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Lỗi", f"Không ghi được file:\n{e}")
                return
            self._them_gan_day(duong)
            self.log_write(f"[Dự án] Đã lưu {duong}\n")
            self.statusBar().showMessage(f"Đã lưu dự án: {duong}")

        def mo_du_an(self, duong):
            """Mở file dự án .tachrang: DICOM + kết quả + scan trở lại bằng 1 thao tác."""
            f = Path(duong)
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                case = str(data["case"])
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self, "Không mở được dự án",
                    f"File dự án hỏng hoặc không đúng định dạng:\n{f}\n\n{e}")
                return False
            out_dir = str(data.get("out_dir") or "")
            # File nằm trong <kết quả>/du_an/ -> tự suy ra out kể cả khi đã dời thư mục
            if not Path(out_dir).is_dir() and f.parent.name == "du_an":
                out_dir = str(f.parent.parent)
            if Path(out_dir).is_dir():
                self.out_edit.setText(out_dir)
                self.settings.setValue("out_dir", out_dir)
            self._them_gan_day(str(f))
            scan = {h: str(data.get(f"scan_{h}") or "") for h in ("tren", "duoi")}
            scan = {h: p for h, p in scan.items() if p and Path(p).is_file()}
            dicom = str(data.get("dicom_dir") or "")
            if dicom and Path(dicom).is_dir():
                dicom = str(Path(dicom))
                if dicom == (self._da_nap or ""):      # DICOM này đang mở sẵn
                    for h, p in scan.items():
                        (self.scan_edit_tren if h == "tren"
                         else self.scan_edit_duoi).setText(p)
                    self._ca_hien = ""
                    self.refresh_cases(auto_render=True)
                    return True
                self._scan_cho = {"case": case, **scan}
                self.in_edit.setText(dicom)
                self.settings.setValue("in_dir", dicom)
                self.log_write(f"[Dự án] Mở {f.name}: nạp DICOM + kết quả ca {case}\n")
                self.nap_dicom(dicom)      # xong sẽ tự nạp kết quả + scan đã căn
                return True
            # Mất thư mục DICOM gốc: vẫn mở phần kết quả (CT nền lấy từ staged_inputs)
            for h, p in scan.items():
                (self.scan_edit_tren if h == "tren" else self.scan_edit_duoi).setText(p)
            self._ct_case = case
            self._ca_hien = ""
            self.refresh_cases(auto_render=True)
            self.log_write(f"[Dự án] {f.name}: thư mục DICOM gốc không còn "
                           f"({dicom or 'chưa ghi'}) — mở phần kết quả của ca {case}.\n")
            self.statusBar().showMessage(
                f"Dự án {case}: DICOM gốc không còn — đã mở phần kết quả")
            return True

        def _mo_du_an_dialog(self):
            ds = self._ds_gan_day()
            bat_dau = (str(Path(ds[0]).parent) if ds
                       else str(Path(self.out_edit.text().strip() or ".") / "du_an"))
            f, _ = QtWidgets.QFileDialog.getOpenFileName(
                self, "Mở dự án TachRang", bat_dau,
                "Dự án TachRang (*.tachrang);;Tất cả (*)")
            if f:
                self.mo_du_an(f)

        # Danh sách dự án gần đây (QSettings) — chỉ giữ file còn tồn tại
        def _ds_gan_day(self):
            v = self.settings.value("du_an_gan_day", [])
            if isinstance(v, str):
                v = [v] if v else []
            return [p for p in (v or []) if Path(p).is_file()]

        def _them_gan_day(self, duong):
            duong = str(Path(duong))
            ds = [p for p in self._ds_gan_day()
                  if p.casefold() != duong.casefold()]
            self.settings.setValue("du_an_gan_day", [duong] + ds[:9])

        def _dung_menu_gan_day(self):
            m = self._menu_gan_day
            m.clear()
            ds = self._ds_gan_day()
            if not ds:
                m.addAction("(Chưa có dự án nào — nạp một ca là tự có)").setEnabled(False)
                return
            for p in ds:
                p = Path(p)
                ten = p.name[:-9] if p.name.endswith(".tachrang") else p.name
                ghi = ""
                try:
                    d = json.loads(p.read_text(encoding="utf-8"))
                    ten = d.get("case") or ten
                    out = Path(d.get("out_dir") or p.parent.parent)
                    if (out / "labelmaps" / f"{ten}.lam-do.nii.gz").is_file():
                        ghi = "   • có bản làm dở"
                    elif (out / "stl" / ten).is_dir() and any((out / "stl" / ten).glob("*.stl")):
                        ghi = "   • có kết quả"
                except Exception:
                    pass
                a = m.addAction(f"{ten}{ghi}")
                a.setToolTip(str(p))
                a.triggered.connect(lambda checked=False, dd=str(p): self.mo_du_an(dd))
            m.addSeparator()
            m.addAction("Xóa danh sách").triggered.connect(
                lambda checked=False: self.settings.setValue("du_an_gan_day", []))

        # Kéo-thả: nhận mọi thứ, tự đoán loại
        def dragEnterEvent(self, e):
            if e.mimeData().hasUrls():
                e.acceptProposedAction()

        def dropEvent(self, e):
            urls = [u.toLocalFile() for u in e.mimeData().urls() if u.toLocalFile()]
            e.acceptProposedAction()
            for u in urls[:4]:              # tối đa 4 mục/lần (vd scan trên + dưới)
                self.nap_thong_minh(u)

        def nap_thong_minh(self, duong):
            """Nhận 1 đường dẫn bất kỳ (kéo-thả) và tự đoán phải làm gì."""
            p = Path(duong)
            if p.is_dir():
                return self._nap_thu_muc_thong_minh(p)
            ten = p.name.lower()
            if ten.endswith(".tachrang"):
                return self.mo_du_an(p)
            if ten.endswith(".dcm"):
                self.in_edit.setText(str(p.parent))
                self.nap_dicom(str(p.parent))
                return True
            if ten.endswith((".nii.gz", ".nii")):
                return self.mo_file_nhan(str(p))
            if ten.endswith((".stl", ".ply", ".obj")):
                return self._nhan_scan_tha(p)
            QtWidgets.QMessageBox.information(
                self, "Không nhận dạng được",
                f"{p.name}\n\nNhận: thư mục DICOM, file .dcm, dự án .tachrang,\n"
                "bản đồ nhãn .nii.gz, scan hàm .stl/.ply/.obj")
            return False

        def _co_dicom(self, d):
            return next(iter(Path(d).rglob("*.dcm")), None) is not None

        def _nap_thu_muc_thong_minh(self, d):
            d = Path(d)
            # 1) thư mục có file dự án -> mở dự án
            da = sorted(d.glob("*.tachrang"))
            if len(da) == 1:
                return self.mo_du_an(da[0])
            # 2) thư mục kết quả (có labelmaps/ hoặc stl/) -> đặt làm output
            if (d / "labelmaps").is_dir() or (d / "stl").is_dir():
                self.out_edit.setText(str(d))
                self.settings.setValue("out_dir", str(d))
                self._ca_hien = ""
                self.refresh_cases(auto_render=True)
                self.statusBar().showMessage(f"Đã đặt thư mục kết quả: {d}")
                return True
            # 3) DICOM ngay trong thư mục -> nạp luôn
            if any(d.glob("*.dcm")):
                if self.cb_seg.isChecked():
                    self.in_edit.setText(str(d))
                    return True
                self.in_edit.setText(str(d))
                self.settings.setValue("in_dir", str(d))
                self.nap_dicom(str(d))
                return True
            # 4) thư mục cha chứa nhiều ca -> cho chọn 1 ca
            ca = [s for s in sorted(d.iterdir()) if s.is_dir() and self._co_dicom(s)]
            if len(ca) == 1:
                return self._nap_thu_muc_thong_minh(ca[0])
            if ca:
                ten, ok = QtWidgets.QInputDialog.getItem(
                    self, "Chọn ca", f"Thư mục này chứa {len(ca)} ca — chọn một để mở:",
                    [c.name for c in ca], 0, False)
                if ok and ten:
                    return self._nap_thu_muc_thong_minh(d / ten)
                return False
            # 5) .dcm nằm sâu hơn -> nạp thư mục chứa nó; hết cách thì cứ thử đọc DICOM
            hit = next(iter(d.rglob("*.dcm")), None)
            muc = hit.parent if hit else d
            self.in_edit.setText(str(muc))
            self.nap_dicom(str(muc))    # không phải DICOM sẽ báo lỗi dễ hiểu
            return True

        def _nhan_scan_tha(self, p):
            """Thả file scan: đoán hàm theo tên file, không đoán được thì hỏi."""
            p = Path(p)
            ten = p.stem.lower()
            ham = ("tren" if any(k in ten for k in ("maxil", "upper", "tren", "ham_tren", "_u"))
                   else "duoi" if any(k in ten for k in ("mandib", "lower", "duoi", "ham_duoi", "_l"))
                   else None)
            if ham is None:
                box = QtWidgets.QMessageBox(self)
                box.setWindowTitle("Scan hàm nào?")
                box.setText(f"{p.name}\n\nĐây là scan hàm TRÊN hay hàm DƯỚI?")
                b_tren = box.addButton("Hàm trên", QtWidgets.QMessageBox.ButtonRole.AcceptRole)
                b_duoi = box.addButton("Hàm dưới", QtWidgets.QMessageBox.ButtonRole.AcceptRole)
                box.addButton("Hủy", QtWidgets.QMessageBox.ButtonRole.RejectRole)
                box.exec()
                nut = box.clickedButton()
                ham = "tren" if nut is b_tren else "duoi" if nut is b_duoi else None
                if ham is None:
                    return False
            (self.scan_edit_tren if ham == "tren" else self.scan_edit_duoi).setText(str(p))
            self.settings.setValue("thu_muc_scan", str(p.parent))
            self._hien_scan_tho(str(p))
            self.statusBar().showMessage(
                f"Đã nạp scan hàm {'trên' if ham == 'tren' else 'dưới'}: {p.name}")
            return True

        # ── Scan hàm: căn tự động với răng CBCT ─────────────────────────
        def _chon_scan(self, ham):
            """Chọn file scan cho một hàm ('tren'/'duoi'); cảnh báo nếu tên file giống hàm kia."""
            ten_ham = "trên" if ham == "tren" else "dưới"
            bat_dau = str(self.settings.value("thu_muc_scan", str(self._default_in)))
            f, _ = QtWidgets.QFileDialog.getOpenFileName(
                self, f"Chọn file scan hàm {ten_ham}", bat_dau,
                "Scan hàm (*.stl *.ply *.obj);;Tất cả (*)")
            if not f:
                return
            ten = Path(f).stem.lower()
            doan = ("tren" if any(k in ten for k in ("maxil", "upper", "tren", "ham_tren", "_u"))
                    else "duoi" if any(k in ten for k in ("mandib", "lower", "duoi", "ham_duoi", "_l"))
                    else None)
            if doan and doan != ham:
                khac = "trên" if doan == "tren" else "dưới"
                r = QtWidgets.QMessageBox.question(
                    self, "Có vẻ khác hàm",
                    f"Tên file:\n{Path(f).name}\n\ngiống scan hàm {khac.upper()} nhưng bạn đang chọn cho "
                    f"hàm {ten_ham.upper()}.\nVẫn dùng file này?",
                    QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                    QtWidgets.QMessageBox.StandardButton.No)
                if r != QtWidgets.QMessageBox.StandardButton.Yes:
                    return
            (self.scan_edit_tren if ham == "tren" else self.scan_edit_duoi).setText(f)
            self.settings.setValue("thu_muc_scan", str(Path(f).parent))
            self._hien_scan_tho(f)

        def _doc_mesh_vtk(self, path):
            """Đọc STL/PLY/OBJ thành vtkPolyData (None nếu không đọc được)."""
            ext = Path(path).suffix.lower()
            rd = {".stl": vtk.vtkSTLReader, ".ply": vtk.vtkPLYReader,
                  ".obj": vtk.vtkOBJReader}.get(ext)
            if rd is None:
                return None
            r = rd()
            r.SetFileName(str(path))
            r.Update()
            pd = r.GetOutput()
            return pd if pd is not None and pd.GetNumberOfPoints() > 0 else None

        # Danh sách scan: mỗi file = 1 actor + 1 dòng (tích = hiện)
        def _scan_them(self, path, da_can, info=None, hien=True):
            """Thêm (hoặc thay) một scan vào khung 3D + danh sách. Trả về actor/None."""
            path = str(Path(path))
            self._scan_bo_file(path)
            pd = self._doc_mesh_vtk(path)
            if pd is None:
                return None
            mp = vtk.vtkPolyDataMapper()
            mp.SetInputData(pd)
            a = vtk.vtkActor()
            a.SetMapper(mp)
            pr = a.GetProperty()
            pr.SetColor(*((0.35, 0.85, 0.95) if da_can else (1.00, 0.62, 0.25)))
            pr.SetOpacity(0.55)
            pr.SetSpecular(0.3)
            a.SetVisibility(bool(hien))
            self.renderer.AddActor(a)
            info = info or {}
            if da_can:
                q = info.get("chat_luong") or {}
                ten = (f"✔ Đã căn — hàm {info.get('ham', '?')} — "
                       f"sai số {q.get('median_mm', 0):.2f} mm — {Path(path).name}")
                mau = QtGui.QColor(89, 217, 242)
            else:
                ten = f"● Chưa căn (hệ tọa độ scan) — {Path(path).name}"
                mau = QtGui.QColor(255, 158, 64)
            it = QtWidgets.QListWidgetItem(ten)
            it.setFlags(it.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(QtCore.Qt.CheckState.Checked if hien
                             else QtCore.Qt.CheckState.Unchecked)
            it.setData(QtCore.Qt.ItemDataRole.UserRole, path)
            it.setToolTip(path)
            px = QtGui.QPixmap(14, 14)
            px.fill(mau)
            it.setIcon(QtGui.QIcon(px))
            self.ds_scan.blockSignals(True)
            self.ds_scan.addItem(it)
            self.ds_scan.blockSignals(False)
            self.ds_scan.setCurrentItem(it)
            self._scan_items[path] = {"actor": a, "item": it, "da_can": da_can, "info": info,
                                      "pd": pd, "lat": None,
                                      "case": self._ca_hien or self._ct_case}
            self._scan_lat_them(path)
            self._cap_nhat_trang_thai_ham()
            return a

        def _cap_nhat_trang_thai_ham(self):
            """2 ô trạng thái ‘Hàm trên / Hàm dưới’ ở tab Căn Scan: đã căn (sai số) hay chưa."""
            self.lb_ca_scan.setText(
                f"Ca CBCT đang mở: <b>{self._ca_hien}</b>" if self._ca_hien
                else "<i>Chưa mở ca CBCT đã tách — mở ở tab 🦷 Tách răng trước.</i>")
            da = {}
            for d in self._scan_items.values():
                if d["da_can"]:
                    q = (d["info"] or {}).get("chat_luong") or {}
                    da[str((d["info"] or {}).get("ham", ""))] = q.get("median_mm")
            for lb, khoa, ten in ((self.lb_ham_tren, "tren", "Hàm trên"),
                                  (self.lb_ham_duoi, "duoi", "Hàm dưới")):
                if khoa in da:
                    ss = f" — sai số {da[khoa]:.2f} mm" if da[khoa] is not None else ""
                    lb.setText(f"✔ {ten}: đã căn{ss}")
                    lb.setStyleSheet("background:#dff5e3; color:#1b6b34; border:1px solid #9fd3ad; "
                                     "border-radius:4px; font-weight:600; padding:2px 6px;")
                else:
                    lb.setText(f"○ {ten}: chưa căn")
                    lb.setStyleSheet("background:#f6efe6; color:#8a7a63; border:1px dashed #cdbba3; "
                                     "border-radius:4px; padding:2px 6px;")

        # Viền scan trên 3 lát cắt: chuyển mesh sang chỉ số voxel của CT đang hiện
        def _scan_lat_them(self, path):
            d = self._scan_items.get(path)
            n = self.nguon
            if d is None or self._matrix is None or n.ct_u8 is None:
                return
            try:
                V = khung_xem.mesh_sang_chi_so_voxel(d["pd"], self._matrix)
            except Exception as e:
                self.log_write(f"[Scan] Không vẽ được viền scan trên lát: {e}\n")
                return
            mau = (89, 217, 242) if d["da_can"] else (255, 158, 64)
            hien = d["item"].checkState() == QtCore.Qt.CheckState.Checked
            ent = {"V": V, "mau": mau, "hien": hien}
            if d["lat"] is not None:
                # lọc theo identity: dict chứa mảng numpy nên 'in'/'remove' (so ==) sẽ ném ValueError
                n.scans[:] = [s for s in n.scans if s is not d["lat"]]
            d["lat"] = ent
            n.scans.append(ent)
            self._scan_lat_doi()

        def _scan_lat_doi(self):
            n = self.nguon
            n.scan_epoch += 1
            n._scan_cache = {}
            for cv in self.canvases:
                cv.update()

        def _scan_cap_nhat_lat(self):
            """CT đổi (ca khác / ma trận khác) -> tính lại viền mọi scan."""
            self.nguon.scans = []
            for p in list(self._scan_items):
                self._scan_items[p]["lat"] = None
                self._scan_lat_them(p)
            self._scan_lat_doi()

        def _scan_bo_file(self, path):
            d = self._scan_items.pop(str(Path(path)), None)
            if d is None:
                return
            self.renderer.RemoveActor(d["actor"])
            lat = d.get("lat")
            if lat is not None:
                # lọc theo identity (xem _scan_lat_them): tránh ValueError numpy khi so ==
                truoc = len(self.nguon.scans)
                self.nguon.scans[:] = [s for s in self.nguon.scans if s is not lat]
                if len(self.nguon.scans) != truoc:
                    self._scan_lat_doi()
            row = self.ds_scan.row(d["item"])
            if row >= 0:
                self.ds_scan.blockSignals(True)
                self.ds_scan.takeItem(row)
                self.ds_scan.blockSignals(False)
            self._cap_nhat_trang_thai_ham()

        def _scan_xoa_het(self, chi_da_can=False):
            for p in list(self._scan_items):
                if not chi_da_can or self._scan_items[p]["da_can"]:
                    self._scan_bo_file(p)

        def _scan_chon(self):
            it = self.ds_scan.currentItem()
            if it is None:
                return None
            return self._scan_items.get(it.data(QtCore.Qt.ItemDataRole.UserRole))

        def _scan_item_doi(self, it):
            d = self._scan_items.get(it.data(QtCore.Qt.ItemDataRole.UserRole))
            if d is not None:
                on = it.checkState() == QtCore.Qt.CheckState.Checked
                d["actor"].SetVisibility(on)
                if d.get("lat") is not None:
                    d["lat"]["hien"] = on
                    self._scan_lat_doi()
                self.vtk_widget.GetRenderWindow().Render()

        def _scan_bo(self):
            """Bỏ scan: scan thô → gỡ khỏi 3D + xóa ô đường dẫn; scan đã căn → hỏi gỡ tạm hay xóa file
            đã căn (không xóa thì mở lại ca sẽ tự nạp lại từ thư mục kết quả)."""
            d = self._scan_chon()
            if d is None:
                # không có dòng đang chọn: lấy dòng duy nhất trong danh sách (nếu có)
                it = self.ds_scan.currentItem() or (self.ds_scan.item(0) if self.ds_scan.count() == 1 else None)
                if it is not None:
                    key = str(it.data(QtCore.Qt.ItemDataRole.UserRole) or "")
                    d = self._scan_items.get(key) or self._scan_items.get(str(Path(key))) if key else None
                    if d is None:                      # dòng mồ côi (không còn dữ liệu) → dọn luôn
                        self.ds_scan.blockSignals(True)
                        self.ds_scan.takeItem(self.ds_scan.row(it))
                        self.ds_scan.blockSignals(False)
                        self._cap_nhat_trang_thai_ham()
                        self.lb_scan.setText("Dòng scan này không còn dữ liệu — đã gỡ khỏi danh sách.")
                        return
                elif len(self._scan_items) == 1:
                    d = next(iter(self._scan_items.values()))
                else:
                    QtWidgets.QMessageBox.information(
                        self, "Bỏ scan", "Hãy chọn một dòng scan trong danh sách trước." if self._scan_items
                        else "Không có scan nào đang nạp.")
                    return
            path = Path(d["item"].data(QtCore.Qt.ItemDataRole.UserRole))
            if not d["da_can"]:
                self._scan_bo_file(str(path))
                for ed in (self.scan_edit_tren, self.scan_edit_duoi):
                    if ed.text().strip() and Path(ed.text().strip()) == path:
                        ed.setText("")
                self.lb_scan.setText("Đã bỏ scan thô khỏi khung 3D.")
                self.vtk_widget.GetRenderWindow().Render()
                return
            box = QtWidgets.QMessageBox(self)
            box.setWindowTitle("Bỏ scan đã căn")
            box.setText(f"{path.name}\n\nScan này đã căn và được lưu trong thư mục kết quả của ca, "
                        "nên mỗi lần mở ca sẽ tự nạp lại.")
            box.setInformativeText("Chọn cách bỏ:")
            nut_an = box.addButton("Gỡ khỏi 3D (tạm)", QtWidgets.QMessageBox.ButtonRole.ActionRole)
            nut_xoa = box.addButton("Xóa file đã căn (.stl + .json)", QtWidgets.QMessageBox.ButtonRole.DestructiveRole)
            nut_huy = box.addButton(QtWidgets.QMessageBox.StandardButton.Cancel)
            box.setDefaultButton(nut_huy)      # Enter/đóng cửa sổ = Hủy, không bao giờ tự xóa file
            box.setEscapeButton(nut_huy)
            box.exec()
            if box.clickedButton() is nut_an:
                self._scan_bo_file(str(path))
                self.lb_scan.setText("Đã gỡ scan khỏi 3D (file vẫn còn; mở lại ca sẽ nạp lại).")
            elif box.clickedButton() is nut_xoa:
                self._scan_bo_file(str(path))
                xoa = [path, path.with_suffix(".json")]
                loi = []
                for f in xoa:
                    try:
                        if f.is_file():
                            f.unlink()
                    except Exception as e:
                        loi.append(f"{f.name}: {e}")
                if loi:
                    QtWidgets.QMessageBox.warning(self, "Không xóa được", "\n".join(loi))
                else:
                    self.lb_scan.setText(f"Đã xóa {path.name} và .json (STL răng, he-toa-do-scan không đổi). "
                                         "Muốn dùng lại thì chọn file scan và căn lại.")
                    self.log_write(f"[Scan] Đã xóa scan đã căn: {path}\n")
            self.vtk_widget.GetRenderWindow().Render()

        # ══ TAB "3Shape OrthoAnalyzer": chọn bệnh nhân/model set từ kho 3Shape, ghép chân răng ══
        # ══ TAB "3Shape OrthoAnalyzer" — bố cục 3 bước, chia dọc kéo được ══
        def _tao_tab_3shape(self):
            from tachrang.core import kho_3shape
            w = QtWidgets.QWidget()
            v = QtWidgets.QVBoxLayout(w)
            v.setSpacing(6)
            v.setContentsMargins(8, 6, 8, 6)

            def buoc(so, chu):
                lb = QtWidgets.QLabel(f"<span style='color:#e07b2e'>{so}</span>&nbsp; {chu}")
                lb.setStyleSheet("font-weight:700; font-size:10pt; color:#33291f; background:transparent;")
                return lb

            def nut_nho(chu, tip=""):
                b = QtWidgets.QPushButton(chu)
                b.setMinimumWidth(0)
                b.setToolTip(tip)
                return b

            # ── ① Bệnh nhân / model set ──
            g1 = QtWidgets.QWidget()
            v1 = QtWidgets.QVBoxLayout(g1)
            v1.setContentsMargins(0, 0, 0, 0)
            v1.setSpacing(4)
            v1.addWidget(buoc("①", "Chọn bệnh nhân → model set đã segment"))
            row = QtWidgets.QHBoxLayout()
            self.kho_edit = QtWidgets.QLineEdit(str(kho_3shape.GOC_MAC_DINH))
            self.kho_edit.setToolTip("Thư mục OrthoData của 3Shape (mỗi bệnh nhân 1 thư mục con)")
            self.kho_edit.setPlaceholderText("Thư mục OrthoData…")
            self.btn_kho_pick = nut_nho("📂", "Chọn thư mục kho 3Shape khác")
            self.btn_kho_moi = nut_nho("⟳", "Đọc lại kho")
            for b in (self.btn_kho_pick, self.btn_kho_moi):
                b.setFixedWidth(34)
            row.addWidget(self.kho_edit, stretch=1)
            row.addWidget(self.btn_kho_pick)
            row.addWidget(self.btn_kho_moi)
            v1.addLayout(row)
            row2 = QtWidgets.QHBoxLayout()
            self.kho_tim = QtWidgets.QLineEdit("")
            self.kho_tim.setPlaceholderText("🔎 Tìm tên / mã bệnh nhân…")
            self.kho_tim.setClearButtonEnabled(True)
            self.btn_kho_goiy = nut_nho("★ Theo ca đang mở",
                                        "Tự chọn bệnh nhân có tên/mã giống ca CBCT / thư mục DICOM đang mở")
            row2.addWidget(self.kho_tim, stretch=1)
            row2.addWidget(self.btn_kho_goiy)
            v1.addLayout(row2)
            self.cay_kho = QtWidgets.QTreeWidget()
            self.cay_kho.setHeaderLabels(["Bệnh nhân / model set", "Răng", "Ngày", "Ghép"])
            hd = self.cay_kho.header()
            hd.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
            hd.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
            hd.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
            hd.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
            hd.setStretchLastSection(False)
            self.cay_kho.setRootIsDecorated(True)
            self.cay_kho.setAlternatingRowColors(True)
            self.cay_kho.setMinimumHeight(110)
            self.cay_kho.setToolTip("Nháy đúp model set để xem chi tiết. Chỉ model set có răng đã segment mới ghép được.")
            v1.addWidget(self.cay_kho, stretch=1)
            self.lb_ms_chon = QtWidgets.QLabel("Chưa chọn model set.")
            self.lb_ms_chon.setWordWrap(True)
            self.lb_ms_chon.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
            self.lb_ms_chon.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignLeft)
            self.lb_ms_chon.setStyleSheet("color:#33291f; font-size:9pt; background:#fff3e6; padding:5px;")
            cuon_ms = QtWidgets.QScrollArea()
            cuon_ms.setWidget(self.lb_ms_chon)
            cuon_ms.setWidgetResizable(True)          # chữ dài → cuộn dọc, không bị cắt
            cuon_ms.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            cuon_ms.setMinimumHeight(56)
            cuon_ms.setMaximumHeight(150)
            cuon_ms.setStyleSheet("QScrollArea{background:#fff3e6; border:1px solid #e3d9ca; border-radius:6px;}")
            v1.addWidget(cuon_ms)

            # ── ② Đối chiếu từng răng ──
            g2 = QtWidgets.QWidget()
            v2 = QtWidgets.QVBoxLayout(g2)
            v2.setContentsMargins(0, 0, 0, 0)
            v2.setSpacing(4)
            row_t = QtWidgets.QHBoxLayout()
            row_t.addWidget(buoc("②", "Đối chiếu răng 3Shape ↔ CBCT"), stretch=1)
            self.btn_3s_doichieu = QtWidgets.QPushButton("🔍 Đối chiếu && xem trước")
            self.btn_3s_doichieu.setToolTip(
                "Tính cặp răng theo bề mặt trùng, ghép thử ra thư mục tạm (KHÔNG ghi vào 3Shape) và hiện\n"
                "3 lớp trong khung 3D. Đổi cặp trong bảng rồi bấm lại để xem; hài lòng mới bấm Ghép ở ③.")
            row_t.addWidget(self.btn_3s_doichieu)
            v2.addLayout(row_t)
            row_l = QtWidgets.QHBoxLayout()
            row_l.setSpacing(10)

            def o_lop(chu, mau, tip):
                cb = QtWidgets.QCheckBox(chu)
                cb.setChecked(True)
                cb.setToolTip(tip)
                cb.setStyleSheet(f"QCheckBox{{color:{mau}; font-weight:600; background:transparent;}}")
                cb.toggled.connect(self._3s_lop_doi)
                row_l.addWidget(cb)
                return cb
            row_l.addWidget(QtWidgets.QLabel("Lớp 3D:"))
            self.cb_lop_3s = o_lop("3Shape", "#7a7a6e", "Răng đã segment của 3Shape (trắng)")
            self.cb_lop_cbct = o_lop("CBCT", "#1f6feb", "Răng có chân từ CBCT (màu theo răng)")
            self.cb_lop_ghep = o_lop("Đã ghép", "#1e823c", "Thân 3Shape + chân CBCT như sẽ ghi (xanh lá)")
            row_l.addStretch(1)
            self.cb_chi_rang_chon = QtWidgets.QCheckBox("Chỉ răng chọn")
            self.cb_chi_rang_chon.setToolTip("Ẩn các răng khác để soi kỹ răng đang chọn trong bảng")
            self.cb_chi_rang_chon.toggled.connect(self._3s_lop_doi)
            row_l.addWidget(self.cb_chi_rang_chon)
            v2.addLayout(row_l)
            self.bang_cap = QtWidgets.QTableWidget(0, 4)
            self.bang_cap.setHorizontalHeaderLabels(["Răng", "Răng CBCT lấy chân", "Trùng", ""])
            hb = self.bang_cap.horizontalHeader()
            hb.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
            hb.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
            hb.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
            hb.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Fixed)
            self.bang_cap.setColumnWidth(3, 26)
            hb.setStretchLastSection(False)
            self.bang_cap.verticalHeader().setVisible(False)
            self.bang_cap.verticalHeader().setDefaultSectionSize(26)
            self.bang_cap.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
            self.bang_cap.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
            self.bang_cap.setMinimumHeight(120)
            self.bang_cap.setToolTip("Mỗi dòng 1 răng 3Shape (số FDI). Cột 2: răng CBCT sẽ lấy chân — đổi được, "
                                     "chọn '— bỏ qua —' để không ghép.\nChọn dòng → 3D tô sáng răng đó, 3 lát cắt nhảy tới răng.")
            self.bang_cap.currentCellChanged.connect(lambda r, c, pr, pc: self._3s_chon_dong(r))
            v2.addWidget(self.bang_cap, stretch=1)
            self.lb_dong_cap = QtWidgets.QLabel("")
            self.lb_dong_cap.setWordWrap(True)
            self.lb_dong_cap.setStyleSheet("color:#8a7a63; font-size:9pt; background:transparent;")
            v2.addWidget(self.lb_dong_cap)

            self.chia_3s = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
            self.chia_3s.setChildrenCollapsible(False)
            self.chia_3s.setHandleWidth(6)
            self.chia_3s.addWidget(g1)
            self.chia_3s.addWidget(g2)
            self.chia_3s.setSizes([260, 300])
            v.addWidget(self.chia_3s, stretch=1)

            # ── ③ Ghi vào 3Shape ──
            g3 = QtWidgets.QFrame()
            g3.setObjectName("khung3s")
            g3.setStyleSheet("#khung3s{background:#fffdf9; border:1px solid #e3d9ca; border-radius:8px;} "
                             "#khung3s QLabel{border:none; background:transparent;}")
            v3 = QtWidgets.QVBoxLayout(g3)
            v3.setContentsMargins(8, 6, 8, 8)
            v3.setSpacing(5)
            row3 = QtWidgets.QHBoxLayout()
            row3.addWidget(buoc("③", "Ghi vào 3Shape"), stretch=1)
            row3.addWidget(QtWidgets.QLabel("Khe cổ răng"))
            self.spin_gap = QtWidgets.QDoubleSpinBox()
            self.spin_gap.setRange(0.1, 2.0)
            self.spin_gap.setSingleStep(0.1)
            self.spin_gap.setValue(0.4)
            self.spin_gap.setSuffix(" mm")
            self.spin_gap.setFixedWidth(96)
            self.spin_gap.setToolTip("Chân CBCT bắt đầu thấp hơn đường biên thân răng 3Shape khoảng này")
            row3.addWidget(self.spin_gap)
            v3.addLayout(row3)
            self.lb_ca_3s = QtWidgets.QLabel("")
            self.lb_ca_3s.setStyleSheet("color:#8a7a63; font-size:9pt; background:transparent;")
            v3.addWidget(self.lb_ca_3s)
            self.btn_3s_ghep = QtWidgets.QPushButton("🦷  Ghép chân răng vào model set đã chọn")
            self.btn_3s_ghep.setObjectName("run")
            self.btn_3s_ghep.setMinimumHeight(34)
            self.btn_3s_ghep.setToolTip(
                "Thay chân ảo của từng răng đã segment bằng chân thật CBCT; thân răng 3Shape giữ nguyên.\n"
                "Dùng các cặp trong bảng ② nếu đã đối chiếu. Cần: ca đã tách + đã căn scan (tab ⇄ Căn scan); OrthoAnalyzer ĐÃ ĐÓNG.\n"
                "Tự sao lưu toàn bộ thư mục bệnh nhân trước khi ghi.")
            v3.addWidget(self.btn_3s_ghep)
            row5 = QtWidgets.QHBoxLayout()
            self.btn_3s_khoiphuc = nut_nho("↩ Khôi phục…", "Chép lại toàn bộ file của bệnh nhân từ một bản sao lưu trong backup_3shape/")
            self.btn_3s_thumuc = nut_nho("📂 Thư mục", "Mở thư mục model set")
            self.btn_3s_viewer = nut_nho("👁 3D Viewer", "Mở một răng của model set trong 3Shape 3D Viewer để kiểm tra nhanh")
            for b in (self.btn_3s_khoiphuc, self.btn_3s_thumuc, self.btn_3s_viewer):
                row5.addWidget(b)
            v3.addLayout(row5)
            v.addWidget(g3)
            self.lb_3s = QtWidgets.QLabel("")
            self.lb_3s.setWordWrap(True)
            self.lb_3s.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
            self.lb_3s.setStyleSheet("color:#8a7a63; font-size:9pt; background:transparent;")
            v.addWidget(self.lb_3s)

            self._kho_bn = []
            self._dc = None                      # kết quả doi_chieu() gần nhất
            self._3s_actors = {"3shape": {}, "cbct": {}, "ghep": {}}   # tooth_n -> actor
            self._3s_thu_dir = None
            self.btn_kho_pick.clicked.connect(self._chon_kho_3shape)
            self.btn_kho_moi.clicked.connect(self.nap_kho_3shape)
            self.kho_tim.textChanged.connect(self._loc_kho)
            self.btn_kho_goiy.clicked.connect(self._goi_y_benh_nhan)
            self.cay_kho.currentItemChanged.connect(lambda cur, prev: self._chon_model_set_item(cur))
            self.cay_kho.itemDoubleClicked.connect(lambda it, col: self._chi_tiet_model_set(it))
            self.btn_3s_ghep.clicked.connect(self.ghep_3shape)
            self.btn_3s_doichieu.clicked.connect(self._3s_doi_chieu)
            self.btn_3s_khoiphuc.clicked.connect(self.khoi_phuc_3shape)
            self.btn_3s_thumuc.clicked.connect(self._mo_thu_muc_ms)
            self.btn_3s_viewer.clicked.connect(self._xem_rang_3shape)
            return w

        @staticmethod
        def _ten_ngan(ten):
            """'<ca>_FDI17_upper-right-second-molar.stl' → 'FDI 17'; Rang-them-ham-tren-1 → 'Răng thêm trên 1'."""
            s = Path(ten).stem.split("_", 1)[-1]
            m = re.search(r"FDI(\d\d)", s, re.I)
            if m:
                return f"FDI {m.group(1)}" + (" (dự đoán)" if "du-doan" in s else "")
            s = s.replace("Rang-them-ham-tren", "Răng thêm trên").replace("Rang-them-ham-duoi", "Răng thêm dưới")
            s = s.replace("Rang-ngam-ham-tren", "Răng ngầm trên").replace("Rang-ngam-ham-duoi", "Răng ngầm dưới")
            return s.replace("-", " ")

        def _tabs_an(self):
            """Id các tab người dùng đã tắt (QSettings 'tabs_an', phân cách dấu phẩy)."""
            return [t for t in str(self.settings.value("tabs_an", "") or "").split(",") if t]

        def _dat_tab_hien(self, tid, hien, luu=True):
            """Ẩn/hiện tab theo id trong _tab_muc. Widget vẫn nằm nguyên trong QTabWidget
            nên mọi tham chiếu (setCurrentWidget, `is self._cuon_scan`...) không đổi."""
            wd = next((m[1] for m in self._tab_muc if m[0] == tid), None)
            if wd is None:
                return
            idx = self.tabs_trai.indexOf(wd)
            if not hien and self.tabs_trai.currentIndex() == idx:
                self.tabs_trai.setCurrentWidget(self._tab_muc[0][1])   # về tab chính
            self.tabs_trai.tabBar().setTabVisible(idx, hien)
            if luu:
                an = set(self._tabs_an())
                (an.discard if hien else an.add)(tid)
                self.settings.setValue("tabs_an", ",".join(sorted(an)))

        def _doi_tab_trai(self, i):
            la_3s = self.tabs_trai.widget(i) is self.tab_3shape
            # tab 3Shape có bảng + cây → cho panel trái rộng hơn
            self.tabs_trai.setMaximumWidth(640 if la_3s else 490)
            sp = self.tabs_trai.parentWidget()
            if isinstance(sp, QtWidgets.QSplitter):
                tong = sum(sp.sizes()) or 1320
                trai = 600 if la_3s else 410
                sp.setSizes([trai, max(300, tong - trai)])
            self._che_do_chi_3d(la_3s)
            if la_3s and not self._kho_bn:
                self.nap_kho_3shape()
            if la_3s:
                self.lb_ca_3s.setText(f"Ca CBCT đang mở: <b>{self._ca_hien}</b>" if self._ca_hien
                                      else "<i>Chưa mở ca CBCT — mở ca đã tách (tab 🦷 Tách răng) và căn scan (tab ⇄ Căn scan).</i>")
            if self.tabs_trai.widget(i) is self._cuon_scan:
                self._cap_nhat_trang_thai_ham()
            # lớp xem trước 3Shape tách riêng với lớp của ca: vào tab → ẩn ca + hiện lớp xem trước;
            # rời tab → ẩn lớp xem trước + khôi phục ca đúng theo danh sách tích
            if any(self._3s_actors.values()):
                if la_3s:
                    self._an_hien_lop_ca(False)
                    self._3s_lop_doi()
                else:
                    for ds in self._3s_actors.values():
                        for a in ds.values():
                            a.SetVisibility(False)
                    self._an_hien_lop_ca(True)
                    self.vtk_widget.GetRenderWindow().Render()

        def _che_do_chi_3d(self, bat: bool):
            """Tab 3Shape: ẩn 3 lát cắt CBCT + thanh cửa sổ/khối CBCT, khung 3D chiếm toàn panel phải."""
            if bat and self._co_phai_luu is None:
                self._co_phai_luu = (self.chia_phai.sizes(), self.hang_duoi.sizes())
            self.hang_tren.setVisible(not bat)
            self._o_lat[2].setVisible(not bat)
            self.thanh_cua_so.setVisible(not bat)
            self.thanh_3d.setVisible(not bat)
            if not bat and self._co_phai_luu is not None:
                a, b = self._co_phai_luu
                self._co_phai_luu = None
                self.chia_phai.setSizes(a)
                self.hang_duoi.setSizes(b)
            self.vtk_widget.GetRenderWindow().Render()

        def _chon_kho_3shape(self):
            d = QtWidgets.QFileDialog.getExistingDirectory(
                self, "Thư mục OrthoData của 3Shape", self.kho_edit.text().strip() or "C:\\")
            if d:
                self.kho_edit.setText(d)
                self.nap_kho_3shape()

        def nap_kho_3shape(self):
            from tachrang.core import kho_3shape
            goc = Path(self.kho_edit.text().strip() or str(kho_3shape.GOC_MAC_DINH))
            self.settings.setValue("thu_muc_kho_3shape", str(goc))
            self._kho_bn = kho_3shape.quet_kho(goc)
            self.cay_kho.clear()
            n_ms = 0
            for bn in self._kho_bn:
                it = QtWidgets.QTreeWidgetItem([f"{bn['ho_ten']}  (mã {bn['id']})"
                                                + (f"  [{bn['ma_ngoai']}]" if bn['ma_ngoai'] else ""),
                                                "", "", ""])
                it.setData(0, QtCore.Qt.ItemDataRole.UserRole, {"loai": "bn", "bn": bn})
                f = it.font(0)
                f.setBold(True)
                it.setFont(0, f)
                for ms in bn["model_sets"]:
                    n_ms += 1
                    ghep = ms["da_ghep"]
                    con = QtWidgets.QTreeWidgetItem([
                        f"model set {ms['ten']}" + (f" — {ms['ghi_chu']}" if ms['ghi_chu'] else "")
                        + (f"  ({ms['trang_thai']})" if ms['trang_thai'] else "")
                        + ("  🔒 đang mở" if ms["dang_mo"] else "")
                        + (("  🔐 mã hóa (dựng lại được)" if len(ms.get("rang_dung_lai") or []) == len(ms["rang_ma_hoa"])
                            else "  🔐 răng đã mã hóa") if ms.get("rang_ma_hoa") else ""),
                        str(ms["so_rang"]) if ms["so_rang"] else "—",
                        kho_3shape.mo_ta_ngay(ms["ngay"]),
                        ("✔ " + str(ghep.get("thoi_gian", ""))[:16]) if ghep else ""])
                    con.setData(0, QtCore.Qt.ItemDataRole.UserRole, {"loai": "ms", "bn": bn, "ms": ms})
                    if not ms["so_rang"] or (ms.get("rang_ma_hoa") and
                                              len(ms.get("rang_dung_lai") or []) < len(ms["rang_ma_hoa"])):
                        for c in range(4):
                            con.setForeground(c, QtGui.QBrush(QtGui.QColor(160, 150, 135)))
                        con.setToolTip(0, "Chưa segment răng — không ghép được" if not ms["so_rang"] else
                                       "Có răng 3Shape lưu dạng mã hóa mà không có STL kèm để dựng lại")
                    if ghep:
                        con.setForeground(3, QtGui.QBrush(QtGui.QColor(30, 130, 60)))
                    it.addChild(con)
                self.cay_kho.addTopLevelItem(it)
                it.setExpanded(True)
            self.lb_3s.setText(f"Kho 3Shape: {len(self._kho_bn)} bệnh nhân, {n_ms} model set"
                               + ("" if self._kho_bn else f" — không thấy dữ liệu trong {goc}"))
            if self._ca_hien:
                self._goi_y_benh_nhan(im_lang=True)

        def _loc_kho(self, txt):
            from tachrang.core import kho_3shape
            k = kho_3shape.khoa_so_sanh(txt)
            for i in range(self.cay_kho.topLevelItemCount()):
                it = self.cay_kho.topLevelItem(i)
                bn = it.data(0, QtCore.Qt.ItemDataRole.UserRole)["bn"]
                hop = (not k) or k in kho_3shape.khoa_so_sanh(f"{bn['ho_ten']} {bn['id']} {bn['ma_ngoai']}")
                it.setHidden(not hop)

        def _goi_y_benh_nhan(self, im_lang=False):
            from tachrang.core import kho_3shape
            if not self._kho_bn:
                self.nap_kho_3shape()
            thu_muc = Path(self._da_nap).name if getattr(self, "_da_nap", None) else ""
            gy = kho_3shape.goi_y(self._kho_bn, self._ca_hien or "", thu_muc)
            if not gy:
                if not im_lang:
                    QtWidgets.QMessageBox.information(
                        self, "Gợi ý", "Không có bệnh nhân nào tên/mã giống ca đang mở "
                        f"({self._ca_hien or 'chưa mở ca'}; thư mục DICOM: {thu_muc or '-'}). Hãy chọn tay.")
                return
            diem, bn = gy[0]
            # chọn model set có răng mới nhất của bệnh nhân đó
            for i in range(self.cay_kho.topLevelItemCount()):
                it = self.cay_kho.topLevelItem(i)
                if it.data(0, QtCore.Qt.ItemDataRole.UserRole)["bn"]["duong_dan"] == bn["duong_dan"]:
                    muc_tieu = it
                    for j in range(it.childCount()):
                        c = it.child(j)
                        if c.data(0, QtCore.Qt.ItemDataRole.UserRole)["ms"]["so_rang"]:
                            muc_tieu = c
                            break
                    self.cay_kho.setCurrentItem(muc_tieu)
                    self.cay_kho.scrollToItem(muc_tieu)
                    break
            if not im_lang:
                self.lb_3s.setText(f"Gợi ý: {bn['ho_ten']} (mã {bn['id']}) — độ giống {diem * 100:.0f}%"
                                   + (f"; {len(gy) - 1} ứng viên khác" if len(gy) > 1 else ""))

        def _ms_dang_chon(self):
            it = self.cay_kho.currentItem()
            if it is None:
                return None
            d = it.data(0, QtCore.Qt.ItemDataRole.UserRole) or {}
            return d.get("ms") if d.get("loai") == "ms" else None

        def _chon_model_set_item(self, it):
            from tachrang.core import chan_rang_3shape as c3
            d = (it.data(0, QtCore.Qt.ItemDataRole.UserRole) or {}) if it else {}
            if d.get("loai") != "ms":
                self.lb_ms_chon.setText("Chọn một MODEL SET (dòng con) của bệnh nhân." if d else "Chưa chọn model set.")
                self.btn_3s_ghep.setEnabled(False)
                return
            ms, bn = d["ms"], d["bn"]
            fdi = sorted(c3.universal_sang_fdi(n) for n in ms["rang"])
            dong = [f"<b>{bn['ho_ten']}</b> (mã {bn['id']}) — model set <b>{ms['ten']}</b>, "
                    f"{'hàm trên' if ms['ham_tren'] else ''}{' + ' if ms['ham_tren'] and ms['ham_duoi'] else ''}"
                    f"{'hàm dưới' if ms['ham_duoi'] else ''}"]
            if ms["so_rang"]:
                dong.append(f"{ms['so_rang']} răng đã segment: FDI " + ", ".join(map(str, fdi)))
            else:
                dong.append("<span style='color:#b00'>Chưa segment răng — hãy segment trong OrthoAnalyzer trước.</span>")
            if ms["da_ghep"]:
                g = ms["da_ghep"]
                dong.append(f"<span style='color:#1e823c'>✔ Đã ghép chân CBCT lúc {g.get('thoi_gian', '?')} "
                            f"(ca {g.get('case', '?')}). Ghép lại sẽ thay bằng chân mới.</span>")
            if ms.get("rang_ma_hoa"):
                dl = ms.get("rang_dung_lai") or []
                if len(dl) == len(ms["rang_ma_hoa"]):
                    dong.append(f"<span style='color:#b95d1a'>🔐 {len(dl)} răng đã được 3Shape lưu lại dạng mã hóa "
                                "(sau khi làm mịn / sửa lưới) — phần mềm sẽ dựng lại từ bản STL 3Shape ghi kèm, "
                            "thân/chân phân theo hình học. Chân thậ t của các răng đó (nếu đã ghép) có thể đã bị thay bằng chân ảo → nên ghép lại.</span>")
                else:
                    dong.append(f"<span style='color:#b00'>🔐 {len(ms['rang_ma_hoa']) - len(dl)} răng mã hóa không có STL kèm → "
                                "không đọc/ghép được các răng đó.</span>")
            if ms["dang_mo"]:
                dong.append("<span style='color:#b00'>🔒 Đang mở trong OrthoAnalyzer — phải thoát trước khi ghép.</span>")
            self.lb_ms_chon.setText("<br>".join(dong))
            self.btn_3s_ghep.setEnabled(
                ms["so_rang"] - len(ms.get("rang_ma_hoa") or []) + len(ms.get("rang_dung_lai") or []) > 0)

        def _chi_tiet_model_set(self, it):
            d = it.data(0, QtCore.Qt.ItemDataRole.UserRole) or {}
            if d.get("loai") != "ms":
                return
            ms = d["ms"]
            QtWidgets.QMessageBox.information(
                self, "Model set", f"Thư mục: {ms['duong_dan']}\nNgày: {ms['ngay']}\nTrạng thái: {ms['trang_thai']}\n"
                f"Răng (Universal): {ms['rang']}\n"
                + (f"Đã ghép: {json.dumps(ms['da_ghep'].get('rang', [])[:3], ensure_ascii=False)}..." if ms['da_ghep'] else ""))

        def _mo_thu_muc_ms(self):
            ms = self._ms_dang_chon()
            p = Path(ms["duong_dan"]) if ms else Path(self.kho_edit.text().strip() or ".")
            if p.is_dir():
                os.startfile(str(p))  # noqa: S606

        def _xem_rang_3shape(self):
            ms = self._ms_dang_chon()
            if not ms or not ms["rang"]:
                return
            vw = Path(r"C:\Program Files\3Shape\3DViewer\3Shape_3DViewer.exe")
            if not vw.is_file():
                QtWidgets.QMessageBox.information(self, "Không có 3D Viewer", "Không tìm thấy 3Shape 3D Viewer trên máy.")
                return
            # ưu tiên răng cửa giữa (8/9/24/25), không thì răng đầu
            uu = [n for n in (8, 9, 24, 25) if n in ms["rang"]] or ms["rang"]
            import subprocess
            subprocess.Popen([str(vw), str(Path(ms["duong_dan"]) / f"Tooth_{uu[0]}.dcm")])

        # ── Đối chiếu thủ công: bảng cặp + 3 lớp 3D ────────────────────────────────
        def _3s_kiem_dieu_kien(self):
            """Trả về (ms_dir, out) nếu đủ điều kiện, else None (đã báo)."""
            from tachrang.core import chan_rang_3shape as c3
            ms_info = self._ms_dang_chon()
            ms = ms_info["duong_dan"] if ms_info else ""
            if not ms or not Path(ms).is_dir() or not c3.liet_ke_tooth_dcm(Path(ms)):
                QtWidgets.QMessageBox.information(
                    self, "Thiếu model set", "Hãy chọn một model set ĐÃ SEGMENT RĂNG trong danh sách bệnh nhân.")
                return None
            if not self._ca_hien:
                QtWidgets.QMessageBox.information(self, "Chưa có ca", "Chưa mở ca đã tách răng.")
                return None
            out = self.out_edit.text().strip() or "."
            if not c3.tim_T_theo_ham(Path(out) / "stl" / self._ca_hien):
                QtWidgets.QMessageBox.information(
                    self, "Chưa căn scan",
                    "Ca này chưa căn scan hàm với CBCT (tab ⇄ Căn scan).\n"
                    "Cần căn ít nhất hàm cần ghép để biết vị trí răng CBCT trong hệ tọa độ của 3Shape.")
                return None
            return ms, out

        def _3s_doi_chieu(self):
            dk = self._3s_kiem_dieu_kien()
            if dk is None:
                return
            if self._3s_thread is not None and self._3s_thread.isRunning():
                return
            ms, out = dk
            # đổi model set/ca → bảng cũ vô nghĩa
            if self._dc and (self._dc["ms_dir"] != ms or self._dc["case"] != self._ca_hien):
                self._dc = None
            self.btn_3s_doichieu.setEnabled(False)
            self.lb_3s.setText("Đang đối chiếu răng 3Shape ↔ CBCT ...")
            if self._dc is None:
                self._3s_thread = DoiChieuThread(ms, out, self._ca_hien)
                self._3s_thread.tien_do.connect(self._3s_tien_do)
                self._3s_thread.xong.connect(self._3s_doi_chieu_xong)
                self._3s_thread.start()
            else:
                self._3s_doi_chieu_xong(self._dc, giu_bang=True)

        def _3s_doi_chieu_xong(self, dc, giu_bang=False):
            self.btn_3s_doichieu.setEnabled(True)
            if isinstance(dc, dict) and "loi" in dc and "rang_3s" not in dc:
                self.lb_3s.setText("Lỗi: " + dc["loi"])
                QtWidgets.QMessageBox.warning(self, "Đối chiếu thất bại", dc["loi"])
                return
            self._dc = dc
            if not giu_bang:
                self._3s_dien_bang(dc)
            if not dc["cung_bn"]:
                self.lb_3s.setText(
                    f"CẢNH BÁO: chỉ {dc['khop_tot']}/{dc['so_rang_3s']} răng trùng bề mặt — model set có thể "
                    "KHÔNG cùng bệnh nhân/scan với ca này. Bảng vẫn hiện để bạn tự kiểm tra.")
            else:
                self.lb_3s.setText(f"Đối chiếu: {dc['khop_tot']}/{dc['so_rang_3s']} răng khớp tự động. "
                                   "Đang ghép thử để xem trước ...")
            # ghép thử ra thư mục tạm theo cặp hiện có trong bảng → lớp 'Đã ghép'
            import tempfile
            self._3s_thu_dir = Path(tempfile.mkdtemp(prefix="tachrang_3shape_"))
            self._3s_thread = Ghep3ShapeThread(dc["ms_dir"], self.out_edit.text().strip() or ".",
                                                self._ca_hien, float(self.spin_gap.value()),
                                                thu_dir=self._3s_thu_dir, cap_thu_cong=self._3s_cap_tu_bang(),
                                                dc=dc)
            self._3s_thread.tien_do.connect(self._3s_tien_do)
            self._3s_thread.xong.connect(self._3s_xem_truoc_xong)
            self._3s_thread.start()

        def _3s_dien_bang(self, dc):
            from tachrang.core import chan_rang_3shape as c3
            uv = dc["ung_vien"]
            self.bang_cap.blockSignals(True)
            self.bang_cap.setRowCount(0)
            for r in sorted(dc["rang_3s"], key=lambda x: x["fdi"]):
                row = self.bang_cap.rowCount()
                self.bang_cap.insertRow(row)
                it0 = QtWidgets.QTableWidgetItem(f"{r['fdi']}")
                it0.setToolTip(f"Răng 3Shape số {r['tooth']} (Universal) = FDI {r['fdi']}")
                it0.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                it0.setData(QtCore.Qt.ItemDataRole.UserRole, r["tooth"])
                it0.setFlags(it0.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                self.bang_cap.setItem(row, 0, it0)
                cb = ComboKhongLan()
                cb.addItem("— bỏ qua —", None)
                # ứng viên cùng hàm, sắp theo điểm; các răng khác cùng hàm xếp sau
                diem = {j: dm for dm, j in r.get("diem", [])}
                cung_ham = [j for j, u in enumerate(uv) if u["ham"] == r.get("ham")]
                cung_ham.sort(key=lambda j: -diem.get(j, -1))
                for j in cung_ham:
                    u = uv[j]
                    dm = diem.get(j)
                    cb.addItem(self._ten_ngan(u["ten"]) + (f"   {dm * 100:.0f}%" if dm is not None else ""), u["ten"])
                    cb.setItemData(cb.count() - 1, u["ten"], QtCore.Qt.ItemDataRole.ToolTipRole)
                if r["chon"] is not None:
                    cb.setCurrentIndex(cb.findData(uv[r["chon"]]["ten"]))
                cb.setProperty("tooth", r["tooth"])
                cb.currentIndexChanged.connect(self._3s_bang_doi)
                self.bang_cap.setCellWidget(row, 1, cb)
                it2 = QtWidgets.QTableWidgetItem(f"{r['khop'] * 100:.0f}%" if r["chon"] is not None else "—")
                it2.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                it2.setFlags(it2.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                self.bang_cap.setItem(row, 2, it2)
                ghi = r.get("loi", "")
                if r["chon"] is not None:
                    u = uv[r["chon"]]
                    if u["fdi"] is None:
                        ghi = "Răng CBCT chưa có số FDI (răng thêm) — vẫn ghép vì trùng bề mặt; nên đổi tên vùng ở mục ③"
                    elif u["fdi"] != r["fdi"]:
                        ghi = f"Tên file CBCT ghi FDI{u['fdi']} ≠ số răng 3Shape ({r['fdi']}) — tin hình học, ghép theo 3Shape"
                    elif "du-doan" in u["ten"]:
                        ghi = "Số FDI của CBCT là dự đoán"
                    if r.get("dung_lai"):
                        ghi = (ghi + "; " if ghi else "") + "Răng 3Shape đã mã hóa (đã làm mịn) → dựng lại từ STL kèm"
                elif not ghi:
                    best = r["diem"][0] if r.get("diem") else None
                    ghi = (f"Không răng CBCT nào trùng ≥{c3.NGUONG_KHOP * 100:.0f}% (tốt nhất {best[0] * 100:.0f}%) — "
                           "CBCT thiếu răng hoặc tách/căn chưa đúng" if best else "Không có răng CBCT cùng hàm ở gần")
                self._3s_dat_trang_thai(row, ghi, loi=r["chon"] is None)
            self.bang_cap.blockSignals(False)
            if self.bang_cap.rowCount():
                self.bang_cap.setCurrentCell(0, 0)

        def _3s_dat_trang_thai(self, row, ghi, loi=False, canh_bao=None):
            """Cột 4 = biểu tượng (✔ / ⚠ / ✖) + tooltip; ghi chú đầy đủ lưu trong UserRole."""
            if canh_bao is None:
                canh_bao = bool(ghi) and not loi
            it3 = QtWidgets.QTableWidgetItem("✖" if loi else ("⚠" if canh_bao else "✔"))
            it3.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            it3.setFlags(it3.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
            it3.setForeground(QtGui.QBrush(QtGui.QColor(176, 0, 0) if loi else
                                           (QtGui.QColor(185, 93, 26) if canh_bao else QtGui.QColor(30, 130, 60))))
            it3.setToolTip(ghi or "Khớp tốt")
            it3.setData(QtCore.Qt.ItemDataRole.UserRole, ghi or "")
            self.bang_cap.setItem(row, 3, it3)

        def _3s_cap_tu_bang(self):
            """{tooth_n: tên STL CBCT | None} theo bảng (None nếu bảng rỗng → tự động)."""
            if self.bang_cap.rowCount() == 0:
                return None
            cap = {}
            for row in range(self.bang_cap.rowCount()):
                n = self.bang_cap.item(row, 0).data(QtCore.Qt.ItemDataRole.UserRole)
                cb = self.bang_cap.cellWidget(row, 1)
                cap[int(n)] = cb.currentData() if cb else None
            return cap

        def _3s_bang_doi(self, _i):
            """Người dùng đổi cặp trong bảng → cập nhật cột 'Trùng', đánh dấu răng CBCT dùng 2 lần."""
            if self._dc is None:
                return
            uv = self._dc["ung_vien"]
            diem_theo_tooth = {r["tooth"]: {uv[j]["ten"]: dm for dm, j in r.get("diem", [])}
                               for r in self._dc["rang_3s"]}
            dung = {}
            for row in range(self.bang_cap.rowCount()):
                n = int(self.bang_cap.item(row, 0).data(QtCore.Qt.ItemDataRole.UserRole))
                ten = self.bang_cap.cellWidget(row, 1).currentData()
                dm = diem_theo_tooth.get(n, {}).get(ten)
                self.bang_cap.item(row, 2).setText("—" if ten is None else
                                                   (f"{dm * 100:.0f}%" if dm is not None else "?"))
                if ten is None:
                    self._3s_dat_trang_thai(row, "Bỏ qua theo chọn tay — răng này giữ chân ảo của 3Shape", loi=True)
                elif dm is not None and dm < 0.6:
                    self._3s_dat_trang_thai(row, f"Chọn tay: răng CBCT này chỉ trùng {dm * 100:.0f}% bề mặt thân — "
                                                 "kiểm tra kỹ trong 3D", canh_bao=True)
                else:
                    self._3s_dat_trang_thai(row, "Cặp chọn tay (răng CBCT ở xa, không có điểm trùng)" if dm is None else "",
                                            canh_bao=dm is None)
                if ten:
                    dung.setdefault(ten, []).append(row)
            for ten, rows in dung.items():
                if len(rows) > 1:
                    for row in rows:
                        self._3s_dat_trang_thai(
                            row, f"Răng CBCT {self._ten_ngan(ten)} đang chọn cho {len(rows)} răng 3Shape — "
                                 "chỉ răng đầu được ghép, hãy sửa lại", loi=True)
            self._3s_hien_ghi_chu_dong()
            self.lb_3s.setText("Đã đổi cặp — bấm 'Đối chiếu & xem trước' để ghép thử lại, hoặc 'Ghép' ở ③ để ghi.")

        def _3s_hien_ghi_chu_dong(self):
            """Ghi chú đầy đủ của dòng đang chọn hiện dưới bảng (bảng chỉ để biểu tượng)."""
            row = self.bang_cap.currentRow()
            if row < 0 or self.bang_cap.item(row, 0) is None or self.bang_cap.item(row, 3) is None:
                self.lb_dong_cap.setText("")
                return
            ghi = self.bang_cap.item(row, 3).data(QtCore.Qt.ItemDataRole.UserRole) or "Khớp tốt, không có gì cần lưu ý."
            cb = self.bang_cap.cellWidget(row, 1)
            ten = cb.currentData() if cb else None
            self.lb_dong_cap.setText(f"<b>Răng {self.bang_cap.item(row, 0).text()}</b> ← "
                                     f"{self._ten_ngan(ten) if ten else 'bỏ qua'}: {ghi}")

        def _3s_xem_truoc_xong(self, bc):
            if "loi" in bc:
                self.lb_3s.setText("Lỗi ghép thử: " + bc["loi"])
                return
            ok = [r for r in bc["rang"] if "loi" not in r]
            self.lb_3s.setText(f"Xem trước: {len(ok)}/{len(bc['rang'])} răng ghép được. Trắng = 3Shape, "
                               "màu = CBCT, xanh lá = đã ghép (chân thật). Kiểm tra rồi bấm 'Ghép'.")
            self._3s_hien_3_lop(bc)

        def _3s_xoa_lop(self):
            for lop in self._3s_actors.values():
                for a in lop.values():
                    self.renderer.RemoveActor(a)
                lop.clear()

        def _3s_hien_3_lop(self, bc):
            """Đưa 3 lớp xem trước vào khung 3D. Lớp nào cũng là actor RIÊNG của tab 3Shape
            (răng CBCT chỉ mượn mapper của actor ca) → bật/tắt không ảnh hưởng lớp tab tách răng."""
            dc = self._dc
            if dc is None:
                return
            self._3s_xoa_lop()
            T_ham = {h: np.asarray(T, float) for h, T in dc["T_ham"].items()}

            def actor_tu(V, F, mau, opacity):
                pd = self._pd_tu_numpy(V, F)
                mp = vtk.vtkPolyDataMapper()
                mp.SetInputData(pd)
                a = vtk.vtkActor()
                a.SetMapper(mp)
                a.GetProperty().SetColor(*mau)
                a.GetProperty().SetOpacity(opacity)
                self.renderer.AddActor(a)
                return a

            def actor_muon(a_goc):
                """Actor riêng dùng chung mapper với actor của ca (không copy lưới)."""
                a = vtk.vtkActor()
                a.SetMapper(a_goc.GetMapper())
                a.GetProperty().DeepCopy(a_goc.GetProperty())
                self.renderer.AddActor(a)
                return a

            dung_roi = set()
            for r in dc["rang_3s"]:
                if "ham" not in r:
                    continue
                T = T_ham.get(r["ham"])
                if T is None:
                    continue
                V = r["d"]["V"] @ T[:3, :3].T + T[:3, 3]
                self._3s_actors["3shape"][r["tooth"]] = actor_tu(V, r["d"]["F"], (0.96, 0.96, 0.92), 0.9)
                # răng CBCT tương ứng: actor riêng mượn mapper từ actor của ca (theo tên file)
                if r["chon"] is not None:
                    ten = dc["ung_vien"][r["chon"]]["ten"]
                    k = khoa_ten(Path(ten).stem)
                    a = self._stl_actors.get(k)
                    if a is not None:
                        dung_roi.add(k)
                        self._3s_actors["cbct"][r["tooth"]] = actor_muon(a)
                # răng đã ghép (thư mục tạm)
                f = (self._3s_thu_dir / "Models" / f"Tooth_{r['tooth']}.stl") if self._3s_thu_dir else None
                if f and f.is_file():
                    pd = self._doc_mesh_vtk(f)
                    if pd is not None:
                        from vtk.util.numpy_support import vtk_to_numpy
                        Vg = vtk_to_numpy(pd.GetPoints().GetData()).astype(float)
                        Fg = vtk_to_numpy(pd.GetPolys().GetData()).reshape(-1, 4)[:, 1:]
                        Vg = Vg @ T[:3, :3].T + T[:3, 3]
                        self._3s_actors["ghep"][r["tooth"]] = actor_tu(Vg, Fg, (0.35, 0.80, 0.40), 1.0)
            # răng CBCT không có cặp trong bảng (CBCT thừa răng, vd răng khôn) → cũng vào lớp CBCT
            for k, a in self._stl_actors.items():
                if ("fdi" in k or "rang" in k) and k not in dung_roi:
                    self._3s_actors["cbct"][f"thua-{k}"] = actor_muon(a)
            # chế độ 3Shape: ẩn TOÀN BỘ lớp của ca (không đổi trạng thái tích) — lớp xem trước độc lập
            self._an_hien_lop_ca(False)
            b = [1e9, -1e9, 1e9, -1e9, 1e9, -1e9]
            for a in self._3s_actors["3shape"].values():
                ab = a.GetBounds()
                b = [min(b[0], ab[0]), max(b[1], ab[1]), min(b[2], ab[2]), max(b[3], ab[3]),
                     min(b[4], ab[4]), max(b[5], ab[5])]
            if b[0] < b[1]:
                self.renderer.ResetCamera(b)
            self._3s_lop_doi()

        def _pd_tu_numpy(self, V, F):
            from vtk.util.numpy_support import numpy_to_vtk, numpy_to_vtkIdTypeArray
            pd = vtk.vtkPolyData()
            pts = vtk.vtkPoints()
            pts.SetData(numpy_to_vtk(np.ascontiguousarray(V, dtype=np.float64), deep=True))
            pd.SetPoints(pts)
            cells = np.hstack([np.full((len(F), 1), 3, dtype=np.int64), np.asarray(F, dtype=np.int64)])
            ca = vtk.vtkCellArray()
            ca.SetCells(len(F), numpy_to_vtkIdTypeArray(np.ascontiguousarray(cells.ravel()), deep=True))
            pd.SetPolys(ca)
            nrm = vtk.vtkPolyDataNormals()
            nrm.SetInputData(pd)
            nrm.SplittingOff()
            nrm.Update()
            return nrm.GetOutput()

        def _an_hien_lop_ca(self, hien: bool):
            """Ẩn/hiện toàn bộ lớp 3D của CA CBCT (khối CT, vùng STL, scan) mà KHÔNG đổi trạng thái
            tích trong danh sách. Tab 3Shape dùng lớp xem trước riêng → vào tab ẩn ca, rời tab trả lại."""
            if getattr(self, "volume_actor", None) is not None:
                self.volume_actor.SetVisibility(bool(hien) and self.cb_ct3d.isChecked())
            nhan = getattr(self, "_actors_nhan", {}) or {}
            vis = getattr(self.nguon, "vis_lut", None)
            co_nhan = {id(a) for a in nhan.values()}
            for i, a in nhan.items():
                muon = bool(vis[i]) if vis is not None and i < len(vis) else True
                a.SetVisibility(bool(hien) and muon)
            for a in self._stl_actors.values():        # actor chưa gắn nhãn (hiếm) → theo mặc định hiện
                if id(a) not in co_nhan:
                    a.SetVisibility(bool(hien))
            for d in self._scan_items.values():
                on = d["item"].checkState() == QtCore.Qt.CheckState.Checked
                d["actor"].SetVisibility(bool(hien) and on)

        def _3s_rang_chon(self):
            row = self.bang_cap.currentRow()
            if row < 0 or self.bang_cap.item(row, 0) is None:
                return None
            return int(self.bang_cap.item(row, 0).data(QtCore.Qt.ItemDataRole.UserRole))

        def _3s_lop_doi(self, *_):
            """Bật/tắt 3 lớp; 'Chỉ răng đang chọn' ẩn răng khác; răng chọn hiện đậm."""
            if not any(self._3s_actors.values()):
                return
            chon = self._3s_rang_chon()
            chi_chon = self.cb_chi_rang_chon.isChecked() and chon is not None
            bat = {"3shape": self.cb_lop_3s.isChecked(), "cbct": self.cb_lop_cbct.isChecked(),
                   "ghep": self.cb_lop_ghep.isChecked()}
            for lop, ds in self._3s_actors.items():
                for n, a in ds.items():
                    hien = bat[lop] and (not chi_chon or n == chon)
                    a.SetVisibility(hien)
                    if lop != "cbct":
                        a.GetProperty().SetOpacity((1.0 if n == chon else 0.35) if chon is not None and not chi_chon
                                                   else (0.9 if lop == "3shape" else 1.0))
            self.vtk_widget.GetRenderWindow().Render()

        def _3s_chon_dong(self, row):
            self._3s_lop_doi()
            self._3s_hien_ghi_chu_dong()
            n = self._3s_rang_chon()
            if n is None or self._dc is None:
                return
            # nhảy 3 lát cắt tới tâm răng (hệ CBCT) nếu có CT
            r = next((x for x in self._dc["rang_3s"] if x["tooth"] == n and "than_V" in x), None)
            if r is None or self._matrix is None or self.nguon.ct_u8 is None:
                return
            T = np.asarray(self._dc["T_ham"][r["ham"]], float)
            c = r["than_V"].mean(axis=0) @ T[:3, :3].T + T[:3, 3]
            try:
                M = np.array([[self._matrix.GetElement(i, j) for j in range(4)] for i in range(4)], float)
                Mi = np.linalg.inv(M)
                x, y, z = (c @ Mi[:3, :3].T + Mi[:3, 3])
                for cv in self.canvases:
                    k = int(round({0: z, 1: y, 2: x}[cv.axis]))
                    if 0 <= k < self.nguon.shape[cv.axis]:
                        cv.set_k(k)
            except Exception:
                pass

        def _orthoanalyzer_dang_mo(self, ms_dir: Path):
            if (ms_dir / "lock.lck").exists():
                return True
            try:
                import subprocess
                r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq OrthoAnalyzer.exe", "/NH"],
                                   capture_output=True, text=True, timeout=10)
                return "OrthoAnalyzer.exe" in (r.stdout or "")
            except Exception:
                return False

        def ghep_3shape(self):
            from tachrang.core import chan_rang_3shape as c3
            ms_info = self._ms_dang_chon()
            ms = ms_info["duong_dan"] if ms_info else ""
            if not ms or not Path(ms).is_dir() or not c3.liet_ke_tooth_dcm(Path(ms)):
                QtWidgets.QMessageBox.information(
                    self, "Thiếu model set", "Hãy chọn một model set ĐÃ SEGMENT RĂNG trong danh sách bệnh nhân.")
                return
            if not self._ca_hien:
                QtWidgets.QMessageBox.information(self, "Chưa có ca", "Chưa mở ca đã tách răng.")
                return
            out = self.out_edit.text().strip() or "."
            T_ham = c3.tim_T_theo_ham(Path(out) / "stl" / self._ca_hien)
            if not T_ham:
                QtWidgets.QMessageBox.information(
                    self, "Chưa căn scan",
                    "Ca này chưa căn scan hàm với CBCT (tab ⇄ Căn scan).\n"
                    "Cần căn ít nhất hàm cần ghép để biết vị trí răng CBCT trong hệ tọa độ của 3Shape.")
                return
            if self._orthoanalyzer_dang_mo(Path(ms)):
                QtWidgets.QMessageBox.warning(
                    self, "OrthoAnalyzer đang mở",
                    "Hãy THOÁT HẲN OrthoAnalyzer rồi bấm lại (file răng đang bị khóa; ghi lúc này "
                    "3Shape sẽ ghi đè hoặc báo lỗi).")
                return
            if self._3s_thread is not None and self._3s_thread.isRunning():
                return
            teeth = c3.liet_ke_tooth_dcm(Path(ms))
            ham_txt = " + ".join("hàm trên" if h == "tren" else "hàm dưới" for h in sorted(T_ham))
            ret = QtWidgets.QMessageBox.question(
                self, "Ghép chân răng vào 3Shape",
                f"Model set: {ms}\n{len(teeth)} răng đã segment; ca CBCT: {self._ca_hien} (đã căn {ham_txt}).\n\n"
                "Sẽ: (1) sao lưu TOÀN BỘ thư mục bệnh nhân vào backup_3shape/, (2) thay chân ảo của "
                "từng răng bằng chân thật CBCT, thân răng 3Shape giữ nguyên, (3) cập nhật Models/*.stl.\n"
                "Không đụng file mã hóa/CSDL. Có thể khôi phục bằng nút bên cạnh.\n\nTiếp tục?",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)
            if ret != QtWidgets.QMessageBox.StandardButton.Yes:
                return
            self.btn_3s_ghep.setEnabled(False)
            self.lb_3s.setText("Đang sao lưu và ghép chân răng ...")
            self.log_write(f"[3Shape] Ghép chân răng ca {self._ca_hien} vào {ms}\n")
            self._3s_thread = Ghep3ShapeThread(ms, out, self._ca_hien, float(self.spin_gap.value()))
            self._3s_thread.tien_do.connect(self._3s_tien_do)
            self._3s_thread.xong.connect(self._ghep_3shape_xong)
            self._3s_thread.start()

        def _3s_tien_do(self, s):
            self.lb_3s.setText(s)
            self.statusBar().showMessage("3Shape: " + s)
            self.log_write(f"[3Shape] {s}\n")

        def _ghep_3shape_xong(self, bc):
            self.btn_3s_ghep.setEnabled(True)
            if "loi" in bc:
                self.lb_3s.setText("Lỗi: " + bc["loi"])
                self.log_write(f"[3Shape] Lỗi: {bc['loi']}\n")
                QtWidgets.QMessageBox.warning(self, "Ghép chân răng thất bại", bc["loi"])
                return
            self._3s_xoa_lop()                 # lớp xem trước không còn cần
            self._an_hien_lop_ca(True)         # trả lại lớp của ca đúng theo danh sách tích
            self.vtk_widget.GetRenderWindow().Render()
            ok = [r for r in bc["rang"] if "loi" not in r]
            loi = [r for r in bc["rang"] if "loi" in r]
            cb = [r for r in ok if r.get("canh_bao")]
            self.lb_3s.setText(
                f"Đã ghép {len(ok)}/{len(bc['rang'])} răng. Backup: {bc.get('backup')}\n"
                "Mở lại OrthoAnalyzer → model set này → Virtual Setup để xem chân răng.")
            self.log_write(f"[3Shape] Xong: {len(ok)} răng ghép, {len(loi)} lỗi; backup {bc.get('backup')}\n")
            dong = [f"Đã ghép chân răng CBCT vào {len(ok)} răng."]
            if loi:
                dong.append("Không ghép được: " + "; ".join(
                    f"răng {r['tooth']} (FDI{r['fdi']}): {r['loi']}" for r in loi))
            if cb:
                dong.append("Cảnh báo: " + "; ".join(r["canh_bao"] for r in cb))
            if bc.get("cbct_khong_dung"):
                dong.append("Răng CBCT không có răng 3Shape tương ứng (bỏ qua): "
                            + ", ".join(Path(x).stem.split("_", 1)[-1] for x in bc["cbct_khong_dung"]))
            khop = [r.get("khop", 0) for r in ok]
            if khop:
                dong.append(f"Trùng bề mặt thân răng 3Shape ↔ CBCT: thấp nhất {min(khop) * 100:.0f}%, "
                            f"trung vị {sorted(khop)[len(khop) // 2] * 100:.0f}% (ghép theo hình học, không theo tên file)")
            box = QtWidgets.QMessageBox(self)
            box.setWindowTitle("Ghép chân răng vào 3Shape — xong")
            box.setText("\n".join(dong))
            box.setInformativeText(f"Backup: {bc.get('backup')}\n\nMở lại OrthoAnalyzer để kiểm tra. "
                                   "Nếu có lỗi hiển thị, dùng 'Khôi phục từ backup…'.")
            box.setDetailedText("\n".join(
                f"Tooth_{r['tooth']} (FDI{r['fdi']}) ← {Path(r.get('cbct', '')).stem.split('_', 1)[-1]} "
                f"khớp {r.get('khop', 0) * 100:.0f}%: thân {r.get('facet_than')} + chân {r.get('facet_chan')} facet, "
                f"thể tích {r.get('the_tich_goc_mm3')} → {r.get('the_tich_mm3')} mm³"
                for r in ok))
            nut = box.addButton("Mở thư mục backup", QtWidgets.QMessageBox.ButtonRole.ActionRole)
            box.addButton(QtWidgets.QMessageBox.StandardButton.Ok)
            box.exec()
            if box.clickedButton() is nut and bc.get("backup"):
                os.startfile(bc["backup"])  # noqa: S606
            self.nap_kho_3shape()          # cột "Ghép" ✓ cậ p nhậ t

        def khoi_phuc_3shape(self):
            from tachrang.core import chan_rang_3shape as c3
            goc = Path(self.out_edit.text().strip() or ".").resolve().parent / "backup_3shape"
            d = QtWidgets.QFileDialog.getExistingDirectory(
                self, "Chọn bản sao lưu (backup_3shape\\<mã BN>_<ngày giờ>)",
                str(goc if goc.is_dir() else Path.cwd()))
            if not d:
                return
            nguon_f = Path(d) / "_NGUON.txt"
            if not nguon_f.is_file():
                QtWidgets.QMessageBox.warning(self, "Không phải bản sao lưu",
                                              "Thư mục không có _NGUON.txt (không do TachRang tạo).")
                return
            nguon = Path(nguon_f.read_text(encoding="utf-8").strip())
            if any(self._orthoanalyzer_dang_mo(p) for p in nguon.iterdir() if p.is_dir()) \
                    or self._orthoanalyzer_dang_mo(nguon):
                QtWidgets.QMessageBox.warning(self, "OrthoAnalyzer đang mở",
                                              "Hãy thoát hẳn OrthoAnalyzer rồi khôi phục.")
                return
            ret = QtWidgets.QMessageBox.question(
                self, "Khôi phục", f"Chép lại toàn bộ file từ\n{d}\nvề\n{nguon}\n(ghi đè bản hiện tại)?",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)
            if ret != QtWidgets.QMessageBox.StandardButton.Yes:
                return
            try:
                c3.khoi_phuc(Path(d))
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Khôi phục thất bại", nhat_ky.giai_thich(e))
                return
            self.lb_3s.setText(f"Đã khôi phục về {nguon}")
            self.log_write(f"[3Shape] Đã khôi phục {nguon} từ {d}\n")
            QtWidgets.QMessageBox.information(self, "Đã khôi phục", f"Đã chép lại về {nguon}.")
            self.nap_kho_3shape()

        def _scan_mo_thu_muc(self):
            d = self._scan_chon()
            p = (Path(d["item"].data(QtCore.Qt.ItemDataRole.UserRole)).parent if d
                 else Path(self.out_edit.text().strip() or ".") / "stl" / (self._ca_hien or ""))
            if p.is_dir():
                os.startfile(str(p))  # noqa: S606

        def _scan_xuat(self):
            """Lưu bản scan đã căn ra nơi người dùng chọn (copy file STL đã ở hệ CBCT)."""
            d = self._scan_chon()
            if d is None:
                QtWidgets.QMessageBox.information(self, "Xuất scan",
                                                  "Hãy chọn một scan trong danh sách.")
                return
            src = Path(d["item"].data(QtCore.Qt.ItemDataRole.UserRole))
            if not d["da_can"]:
                QtWidgets.QMessageBox.information(
                    self, "Xuất scan", "Scan này CHƯA căn — file gốc vẫn ở chỗ cũ.\n"
                    "Bấm 'Căn scan với CBCT' trước rồi xuất bản đã căn.")
                return
            bat_dau = str(self.settings.value("thu_muc_xuat_scan", str(src.parent)))
            dich, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Lưu scan đã căn (hệ tọa độ CBCT)", str(Path(bat_dau) / src.name),
                "STL (*.stl)")
            if not dich:
                return
            import shutil
            shutil.copy2(src, dich)
            self.settings.setValue("thu_muc_xuat_scan", str(Path(dich).parent))
            js = src.with_suffix(".json")
            if js.is_file():
                shutil.copy2(js, Path(dich).with_suffix(".json"))
            self.log_write(f"[Scan] Đã xuất {Path(dich).name} (+ .json ma trận)\n")
            self.statusBar().showMessage(f"Đã lưu scan đã căn: {dich}")

        def _scan_xuat_nguoc(self):
            """Đưa STL của ca sang hệ tọa độ scan bằng ma trận đã căn (không căn lại)."""
            d = self._scan_chon()
            if d is None or not d["da_can"]:
                # không chọn -> lấy scan đã căn duy nhất nếu có
                da = [v for v in self._scan_items.values() if v["da_can"]]
                if len(da) == 1:
                    d = da[0]
                else:
                    QtWidgets.QMessageBox.information(
                        self, "STL răng → hệ scan",
                        "Hãy chọn một scan ĐÃ CĂN trong danh sách (cần ma trận căn của nó).")
                    return
            p = Path(d["item"].data(QtCore.Qt.ItemDataRole.UserRole))
            info = d["info"] or {}
            if not info.get("T_scan_sang_cbct"):
                try:
                    info = json.loads(p.with_suffix(".json").read_text(encoding="utf-8"))
                except Exception:
                    info = {}
            T = info.get("T_scan_sang_cbct")
            if T is None:
                QtWidgets.QMessageBox.warning(self, "Thiếu ma trận",
                                              f"Không đọc được ma trận căn trong {p.with_suffix('.json').name}")
                return
            if self._scan_thread is not None and self._scan_thread.isRunning():
                return
            stl_dir = p.parent
            mac_dinh = stl_dir / "he-toa-do-scan"
            dich = QtWidgets.QFileDialog.getExistingDirectory(
                self, "Thư mục ghi STL ở hệ tọa độ scan", str(mac_dinh.parent))
            if not dich:
                return
            dich = Path(dich)
            if dich.resolve() == stl_dir.resolve():
                dich = mac_dinh          # không ghi đè lên STL gốc cùng tên
            # chỉ xuất các vùng đang TÍCH ở mục ③ nếu có danh sách; không thì tất cả
            chon = None
            if self.ds_vung.count() and self.names:
                case = self._case_edit or self._ca_hien
                ten_tick = {khoa_ten(f"{case}_{self.names[i]}") for i in (
                    self.ds_vung.item(r).data(QtCore.Qt.ItemDataRole.UserRole)
                    for r in range(self.ds_vung.count())
                    if self.ds_vung.item(r).checkState() == QtCore.Qt.CheckState.Checked)
                    if i in self.names}
                tat_ca = [f for f in sorted(stl_dir.glob("*.stl")) if "_can-CBCT" not in f.stem]
                chon = [f for f in tat_ca if khoa_ten(f.stem) in ten_tick]
                if not chon:
                    chon = None
            n = len(chon) if chon else len([f for f in stl_dir.glob("*.stl") if "_can-CBCT" not in f.stem])
            self.btn_scan_nguoc.setEnabled(False)
            self.lb_scan.setText(f"Đang đưa {n} STL sang hệ tọa độ scan ...")
            self.log_write(f"[Scan] Xuất {n} STL sang hệ scan -> {dich}\n")
            self._scan_thread = XuatHeScanThread(stl_dir, T, info.get("scan"), dich, chon)
            self._scan_thread.tien_do.connect(self._scan_tien_do)
            self._scan_thread.xong.connect(self._scan_xuat_nguoc_xong)
            self._scan_thread.start()

        def _scan_xuat_nguoc_xong(self, kq):
            self.btn_scan_nguoc.setEnabled(True)
            if "loi" in kq:
                self.lb_scan.setText("Lỗi: " + kq["loi"])
                QtWidgets.QMessageBox.warning(self, "Xuất sang hệ scan thất bại", kq["loi"])
                return
            n = len(kq["files"])
            self.lb_scan.setText(
                f"Đã ghi {n} STL ở HỆ TỌA ĐỘ SCAN + T_cbct_sang_scan.json vào:\n{kq['dich']}\n"
                "Mở các file này cùng file scan GỐC trong phần mềm CAD là khớp vị trí.")
            self.log_write(f"[Scan] Đã ghi {n} STL sang hệ scan: {kq['dich']}\n")
            # cập nhật info để 'Chi tiết' liệt kê
            d = self._scan_chon()
            if d is not None and d["da_can"]:
                d["info"]["xuat_nguoc"] = kq["files"]
            box = QtWidgets.QMessageBox(self)
            box.setWindowTitle("Xuất xong")
            box.setText(f"Đã xuất {n} STL sang hệ tọa độ scan.")
            box.setInformativeText(kq["dich"])
            nut = box.addButton("Mở thư mục", QtWidgets.QMessageBox.ButtonRole.ActionRole)
            box.addButton(QtWidgets.QMessageBox.StandardButton.Ok)
            box.exec()
            if box.clickedButton() is nut:
                os.startfile(kq["dich"])  # noqa: S606

        def _scan_chi_tiet(self):
            """Hộp thoại: căn thế nào, sai số, ma trận, file đã tạo/đổi."""
            d = self._scan_chon()
            if d is None:
                return
            p = Path(d["item"].data(QtCore.Qt.ItemDataRole.UserRole))
            if not d["da_can"]:
                QtWidgets.QMessageBox.information(
                    self, "Scan chưa căn",
                    f"File: {p}\nĐang hiển thị ở hệ tọa độ gốc của máy scan (màu cam).\n"
                    "Chưa có file nào được tạo — bấm 'Căn scan với CBCT'.")
                return
            info = d["info"] or {}
            js = p.with_suffix(".json")
            if not info and js.is_file():
                try:
                    info = json.loads(js.read_text(encoding="utf-8"))
                except Exception:
                    info = {}
            q = info.get("chat_luong") or {}
            T = np.asarray(info.get("T_scan_sang_cbct") or np.eye(4), float)
            R = T[:3, :3]
            goc = np.degrees(np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1)))
            t = T[:3, 3]
            dong = [
                f"<b>Scan gốc:</b> {info.get('scan', '?')}",
                f"<b>Hàm:</b> {info.get('ham', '?')}   <b>Căn thô bằng:</b> {info.get('cach_can_tho', '?')}",
                f"<b>Phép biến đổi scan → CBCT:</b> xoay {goc:.1f}°, tịnh tiến "
                f"({t[0]:.1f}, {t[1]:.1f}, {t[2]:.1f}) mm",
                "<b>Chất lượng khớp thân răng:</b>",
                f"&nbsp;&nbsp;• sai số trung vị {q.get('median_mm', 0):.3f} mm, p90 {q.get('p90_mm', 0):.3f} mm",
                f"&nbsp;&nbsp;• {q.get('ti_le_khop', 0) * 100:.0f}% điểm scan nằm gần răng CBCT (<1 mm), "
                f"{q.get('ti_le_duoi_0p3', 0) * 100:.0f}% trong số đó sai < 0,3 mm",
                f"&nbsp;&nbsp;• {info.get('mo_ta', '')}",
                "<b>File đã tạo:</b>",
                f"&nbsp;&nbsp;+ {p.name}  (scan đã đưa về hệ CBCT — cùng hệ các STL răng)",
                f"&nbsp;&nbsp;+ {js.name}  (ma trận 4×4 + số liệu)",
            ]
            xn = info.get("xuat_nguoc") or []
            if xn:
                dong.append(f"&nbsp;&nbsp;+ he-toa-do-scan/  ({len(xn)} STL của ca đưa sang hệ scan)")
            else:
                dong.append("&nbsp;&nbsp;(không xuất bản STL CBCT sang hệ scan — tích ô bên trên nếu cần)")
            dong.append("<b>File KHÔNG đổi:</b> scan gốc và mọi STL răng/xương của ca giữ nguyên.")
            dong.append(f"<b>Thư mục:</b> {p.parent}")
            box = QtWidgets.QMessageBox(self)
            box.setWindowTitle("Chi tiết phép căn scan")
            box.setTextFormat(QtCore.Qt.TextFormat.RichText)
            box.setText("<br>".join(dong))
            box.setDetailedText("Ma trận T (scan → CBCT):\n" + "\n".join(
                "  ".join(f"{v: .5f}" for v in hang) for hang in T))
            box.exec()

        def _hien_scan_tho(self, f):
            """Vừa chọn file scan: hiện ngay trong 3D ở hệ tọa độ gốc của scan."""
            # bỏ scan CHƯA căn cũ (chỉ giữ 1 scan thô đang chờ căn)
            for p, d in list(self._scan_items.items()):
                if not d["da_can"]:
                    self._scan_bo_file(p)
            a = self._scan_them(f, da_can=False)
            if a is None:
                self.lb_scan.setText("Không đọc được file scan (cần STL/PLY/OBJ có tam giác).")
                return
            n_tri = a.GetMapper().GetInput().GetNumberOfCells()
            b = a.GetBounds()
            kich = (b[1] - b[0], b[3] - b[2], b[5] - b[4])
            # scan và CBCT thường ở 2 hệ tọa độ khác hẳn -> mở rộng camera cho thấy cả hai
            self.renderer.ResetCamera()
            self.vtk_widget.GetRenderWindow().Render()
            self.lb_scan.setText(
                f"Đã nạp scan ({n_tri:,} tam giác, {kich[0]:.0f}×{kich[1]:.0f}×{kich[2]:.0f} mm) — "
                "màu CAM = chưa căn, đang ở hệ tọa độ riêng của máy scan. "
                "Bấm '⇄ Căn hàm ... với răng CBCT' để tính phép đặt.")
            self.log_write(f"[Scan] Đã nạp {Path(f).name} ({n_tri} tam giác) — chưa căn\n")
            self.statusBar().showMessage("Scan (màu cam) đang ở hệ tọa độ riêng — bấm '⇄ Căn hàm ...'")

        def _nap_scan_da_can(self, case):
            """Ca này đã căn scan trước -> tự nạp lại mọi file *_can-CBCT.stl vào danh sách."""
            stl_dir = Path(self.out_edit.text().strip() or ".") / "stl" / case
            fs = sorted(stl_dir.glob(f"{case}_Scan-ham-*_can-CBCT.stl"),
                        key=lambda p: p.stat().st_mtime)
            n = 0
            for f in fs:
                info = {}
                js = f.with_suffix(".json")
                try:
                    from tachrang.core import can_scan
                    info = json.loads(js.read_text(encoding="utf-8"))
                    info["mo_ta"] = can_scan.mo_ta_chat_luong(info["chat_luong"])
                except Exception:
                    pass
                if self._scan_them(f, da_can=True, info=info) is not None:
                    n += 1
            if n:
                self.lb_scan.setText(f"Ca này có {n} scan đã căn (nạp lại từ thư mục kết quả). "
                                     "Nháy đúp một dòng để xem chi tiết.")
            return n > 0

        def can_scan(self, ham):
            """Căn scan của một hàm ('tren'/'duoi') với răng CBCT của ca đang mở."""
            ten_ham = "trên" if ham == "tren" else "dưới"
            ed = self.scan_edit_tren if ham == "tren" else self.scan_edit_duoi
            scan = ed.text().strip()
            if not scan or not Path(scan).is_file():
                QtWidgets.QMessageBox.information(
                    self, "Thiếu file", f"Hãy chọn file scan hàm {ten_ham} trước.")
                return
            if not self._ca_hien:
                QtWidgets.QMessageBox.information(
                    self, "Chưa có ca", "Ca đang mở chưa có răng đã tách để căn.")
                return
            if self._scan_thread is not None and self._scan_thread.isRunning():
                QtWidgets.QMessageBox.information(
                    self, "Đang căn", "Đang căn một scan khác — chờ xong rồi bấm lại.")
                return
            self.btn_can_tren.setEnabled(False)
            self.btn_can_duoi.setEnabled(False)
            self.lb_scan.setText(f"Đang căn hàm {ten_ham}...")
            self.log_write(f"[Scan] Căn {Path(scan).name} (hàm {ten_ham}) với ca {self._ca_hien} ...\n")
            self._scan_thread = CanScanThread(
                scan, self.out_edit.text().strip() or ".", self._ca_hien, ham,
                self.cb_scan_nguoc.isChecked())
            self._scan_thread.tien_do.connect(self._scan_tien_do)
            self._scan_thread.xong.connect(self._can_scan_xong)
            self._scan_thread.start()

        def _scan_tien_do(self, s):
            self.lb_scan.setText(s)
            self.statusBar().showMessage("Scan: " + s)

        def _can_scan_xong(self, kq):
            self.btn_can_tren.setEnabled(True)
            self.btn_can_duoi.setEnabled(True)
            if "loi" in kq:
                self.lb_scan.setText("Lỗi: " + kq["loi"])
                self.log_write(f"[Scan] Lỗi: {kq['loi']}\n")
                QtWidgets.QMessageBox.warning(self, "Căn scan thất bại", kq["loi"])
                return
            q = kq["chat_luong"]
            self.log_write(f"[Scan] {kq['mo_ta']}\n[Scan] Đã ghi: {kq['file_scan_can']}\n"
                           f"[Scan] Đã ghi: {kq.get('file_json', '')}\n")
            if kq.get("xuat_nguoc"):
                self.log_write(f"[Scan] Đã xuất {len(kq['xuat_nguoc'])} STL sang hệ scan "
                               f"(thư mục he-toa-do-scan)\n")
            # Scan thô (màu cam) đã có bản căn -> bỏ khỏi 3D; thêm bản đã căn (xanh lơ)
            for p, d in list(self._scan_items.items()):
                if not d["da_can"]:
                    self._scan_bo_file(p)
            self._scan_them(kq["file_scan_can"], da_can=True, info=kq)
            self.renderer.ResetCamera()
            self.vtk_widget.GetRenderWindow().Render()
            n_file = 2 + len(kq.get("xuat_nguoc") or [])
            self.lb_scan.setText(
                f"Đã căn hàm {kq['ham']} — {kq['mo_ta']}\n"
                f"Đã tạo {n_file} file trong stl/{self._ca_hien}/ (scan đã căn .stl + .json"
                + (" + he-toa-do-scan/" if kq.get("xuat_nguoc") else "") + "). "
                "File scan gốc và STL răng KHÔNG đổi. Bấm 'Chi tiết' để xem ma trận/sai số.")
            self.statusBar().showMessage(
                f"Scan đã căn: sai số trung vị {q['median_mm']:.2f} mm")

        # ── Sáng / tương phản lát cắt ─────────────────────────────────────
        _CUA_SO_SAN = {0: (128.0, 256.0), 1: (185.0, 150.0),
                       2: (150.0, 200.0), 3: (70.0, 120.0)}

        def _ap_cua_so(self, level, window):
            self.nguon.dat_cua_so(level, window)
            for cv in self.canvases:
                cv.update()

        def _chon_cua_so(self, idx):
            if idx in self._CUA_SO_SAN:
                level, window = self._CUA_SO_SAN[idx]
                self._dong_bo_cua_so(level, window, doi_combo=False)
                self._ap_cua_so(level, window)

        def _keo_cua_so(self, _v=None):
            level = 255.0 - self.sl_sang.value()
            window = 608.0 - self.sl_tphan.value()
            self.cb_cua_so.blockSignals(True)
            self.cb_cua_so.setCurrentIndex(4)          # "Tùy chỉnh"
            self.cb_cua_so.blockSignals(False)
            self._ap_cua_so(level, window)

        def _dong_bo_cua_so(self, level, window, doi_combo=True):
            """Kéo chuột phải trên ảnh -> thanh trượt chạy theo."""
            for sl, v in ((self.sl_sang, 255.0 - level),
                          (self.sl_tphan, 608.0 - window)):
                sl.blockSignals(True)
                sl.setValue(int(round(v)))
                sl.blockSignals(False)
            if doi_combo:
                self.cb_cua_so.blockSignals(True)
                self.cb_cua_so.setCurrentIndex(4)
                self.cb_cua_so.blockSignals(False)

        def _ap_kieu_3d(self, idx):
            """Kiểu xem có sẵn: đặt nhanh Ngưỡng + Đậm."""
            nguong, dam = ((120, 28), (185, 55), (55, 16))[int(idx)]
            self.sl_nguong.blockSignals(True)
            self.sl_dam.blockSignals(True)
            self.sl_nguong.setValue(nguong)
            self.sl_dam.setValue(dam)
            self.sl_nguong.blockSignals(False)
            self.sl_dam.blockSignals(False)
            self._chinh_volume()

        def _chinh_volume(self):
            if self.volume_actor is None:
                return
            khung_xem.dat_kieu_volume(self.volume_actor,
                                      float(self.sl_nguong.value()),
                                      self.sl_dam.value() / 100.0)
            self.vtk_widget.GetRenderWindow().Render()

        # ── Chạy pipeline ─────────────────────────────────────────────────
        def on_run(self):
            inp, out = self.in_edit.text().strip(), self.out_edit.text().strip()
            if not inp or not Path(inp).is_dir():
                QtWidgets.QMessageBox.warning(self, "Thiếu thông tin",
                                              "Hãy chọn thư mục DICOM của MỘT bệnh nhân.")
                return
            if not out:
                QtWidgets.QMessageBox.warning(self, "Thiếu thông tin",
                                              "Hãy chọn thư mục kết quả.")
                return
            if not self.cb_seg.isChecked():
                if self.nguon.ct_u8 is None or self._da_nap != str(Path(inp)):
                    if self._dang_nap:
                        QtWidgets.QMessageBox.information(
                            self, "Đang nạp DICOM",
                            "Đang nạp ảnh CBCT — đợi ảnh hiện lên 3 khung lát cắt "
                            "rồi bấm Chạy lại.")
                    else:
                        self.nap_dicom(inp)
                        QtWidgets.QMessageBox.information(
                            self, "Chưa nạp DICOM",
                            "Chương trình đang nạp thư mục này. Khi ảnh hiện lên các "
                            "khung lát cắt, hãy bấm Chạy lần nữa.\n\n"
                            "Lưu ý: mỗi lần chỉ nhận DICOM của MỘT bệnh nhân.")
                    return

            if self.rb_combo.isChecked():
                model = "combo"
            elif self.rb_total.isChecked():
                model = "totalseg"
            elif self.rb_dent.isChecked():
                model = "dentseg"
            else:
                model = "universallab"
            chuong_trinh, dau = lenh_pipeline()
            args = dau + ["-i", inp, "-o", out,
                          "--device", self.device_box.currentText(), "--model", model]
            if self.cb_seg.isChecked():
                args.append("--seg-only")
            else:
                args.append("--single-case")
            if self.cb_bones.isChecked() and model == "totalseg":
                args.append("--include-bones")
            if self.cb_pulp.isChecked() and model in ("totalseg", "combo"):
                args.append("--include-pulp")
            if self.decimate_box.currentText() != "0":
                args += ["--decimate", self.decimate_box.currentText()]

            self.log_write(">>> python " + " ".join(args) + "\n\n")
            self._log_chay = ""           # gộp output để tìm dòng [LOI] khi thất bại
            # Trạng thái đọc tiến độ
            self._n_cases = 0
            self._case_names = []
            self._done_cases = 0
            self._cur_frac = 0.0
            self._bar_completed = False
            self._live_case = None
            self._live_tooth_i = 0
            self._live_first = True
            self._tach_i, self._tach_n = 0, 1    # ca đang tách / tổng ca
            self._dang_tach = False
            self.proc = QtCore.QProcess(self)
            env = QtCore.QProcessEnvironment.systemEnvironment()
            env.insert("PYTHONIOENCODING", "utf-8")
            env.insert("PYTHONUTF8", "1")
            env.insert("PYTHONUNBUFFERED", "1")
            self.proc.setProcessEnvironment(env)
            self.proc.setProcessChannelMode(
                QtCore.QProcess.ProcessChannelMode.MergedChannels)
            self.proc.readyReadStandardOutput.connect(self.on_output)
            self.proc.finished.connect(self.on_finished)
            self.proc.setWorkingDirectory(str(GOC))
            self.proc.start(chuong_trinh, args)

            self.run_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.bar.setRange(0, 0)  # busy cho tới khi biết số ca
            self.bar.setFormat("")
            self.statusBar().showMessage("Đang xử lý...")

        def _set_progress(self, frac, text):
            """Đặt thanh tiến trình 0..1 kèm chữ hiển thị."""
            self.bar.setRange(0, 1000)
            self.bar.setValue(max(0, min(1000, int(frac * 1000))))
            self.bar.setFormat(text)

        def _parse_progress(self, data):
            m = RE_NCASES.search(data)
            if m:
                self._n_cases = int(m.group(1))
                self._case_names = [s.strip() for s in m.group(2).split(",")]
                self._set_progress(0.0, f"Chuẩn bị chạy AI — {self._n_cases} ca")

            for mt in RE_TQDM.finditer(data):
                n, total = int(mt.group(2)), int(mt.group(3))
                if total <= 0:
                    continue
                if n >= total:               # 1 ca vừa chạy AI xong
                    if not self._bar_completed:
                        self._done_cases += 1
                        self._bar_completed = True
                    self._cur_frac = 0.0
                else:
                    self._bar_completed = False
                    self._cur_frac = n / total

            if self._n_cases and not self._dang_tach:
                done = min(self._done_cases, self._n_cases)
                if done >= self._n_cases:
                    self._set_progress(PHAN_AI, f"{int(PHAN_AI * 100)}%  —  AI xong, chuẩn bị tách răng...")
                else:
                    overall = (done + self._cur_frac) / self._n_cases * PHAN_AI
                    name = ""
                    if done < len(self._case_names):
                        name = self._case_names[done]
                        if len(name) > 24:
                            name = name[:22] + "…"
                    self._set_progress(
                        overall,
                        f"{int(overall * 100)}%  —  AI ca {done + 1}/{self._n_cases}: {name}")

            if "[3/3]" in data:
                self._dang_tach = True
                self._set_progress(PHAN_AI, f"{int(PHAN_AI * 100)}%  —  Bắt đầu tách răng...")
            for m in RE_TACH_CA.finditer(data):
                self._tach_i, self._tach_n = int(m.group(1)) - 1, max(int(m.group(2)), 1)
            for m in RE_TACH.finditer(data):
                pct = int(m.group(1)) / 100.0
                # Bước tách chiếm (1-PHAN_AI) của thanh, chia đều cho các ca
                overall = PHAN_AI + (1 - PHAN_AI) * (self._tach_i + pct) / self._tach_n
                ca = f" ca {self._tach_i + 1}/{self._tach_n}" if self._tach_n > 1 else ""
                self._set_progress(
                    overall,
                    f"{int(overall * 100)}%  —  Tách răng{ca} {int(pct * 100)}%: {m.group(2).strip()}")
            if "Xong:" in data:
                self._set_progress(1.0, "Hoàn tất 100%")

        def on_output(self):
            data = bytes(self.proc.readAllStandardOutput()).decode("utf-8", errors="replace")
            self.log_write(data)
            self._log_chay = (self._log_chay + data)[-200000:]
            self._parse_progress(data)
            self._live_update(data)

        def _live_update(self, data):
            """Khung 3D hiện dần từng cấu trúc ngay khi pipeline tách xong nó."""
            for m in RE_SPLIT_CASE.finditer(data):
                self._live_case = m.group(1).strip()
                self._live_tooth_i = 0
                self._live_first = True
                self.renderer.RemoveAllViewProps()
                if self.volume_actor is not None and self._live_case == self._ct_case:
                    self.renderer.AddVolume(self.volume_actor)
                    self.volume_actor.SetVisibility(self.cb_ct3d.isChecked())
                self.hint.SetInput(f"Dang tach: {self._live_case} ...")
                self.renderer.AddActor2D(self.hint)
                self.vtk_widget.GetRenderWindow().Render()
            if not self._live_case:
                return
            out = self.out_edit.text().strip()
            for m in RE_STL_ADD.finditer(data):
                f = Path(out) / "stl" / self._live_case / m.group(1)
                if not f.is_file():
                    continue
                actor, self._live_tooth_i = actor_for_stl(f, self._live_tooth_i)
                self.renderer.AddActor(actor)
                if self._live_first:
                    self.renderer.ResetCamera()
                    self._live_first = False
                self.renderer.ResetCameraClippingRange()
            self.vtk_widget.GetRenderWindow().Render()

        def on_finished(self, code, _status):
            if code == 0:
                self._set_progress(1.0, "Hoàn tất 100%")
            else:
                self._set_progress(0.0, f"Kết thúc — mã lỗi {code}")
            self.run_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.proc = None
            self.refresh_cases(auto_render=True)   # ← tự hiển thị 3D
            if code == 0:
                self.log_write("\n=== HOÀN TẤT ===\n")
                self.statusBar().showMessage("Hoàn tất — kết quả đang hiển thị bên phải")
            else:
                self.log_write(f"\n=== KẾT THÚC (mã lỗi {code}) ===\n")
                self.statusBar().showMessage(f"Kết thúc với mã lỗi {code}")
                self._bao_loi_pipeline(code)

        def _bao_loi_pipeline(self, code):
            """Pipeline thất bại: hiện hộp thoại dễ hiểu thay vì chỉ có mã lỗi trong log."""
            if code == 130 or "[Đã dừng theo yêu cầu]" in self._log_chay[-500:]:
                return
            cau, duong_log = nhat_ky.tach_loi_tu_log(self._log_chay)
            if not cau:
                # tiến trình chết không kịp in [LOI] (bị hệ điều hành giết vì hết RAM, crash thư viện...)
                duoi = self._log_chay[-4000:]
                if "MemoryError" in duoi or "bad allocation" in duoi or code in (-1073741819, 3221225477, -1073740791):
                    cau = ("Tiến trình AI bị dừng đột ngột — thướng do HẾT RAM/VRAM với ảnh lớn. "
                           "Hãy đóng chương trình khác, thử chế độ DentalSegmentator hoặc Thiết bị = cpu.")
                else:
                    cau = "Quá trình tách răng dừng với lỗi không xác định. Xem chi tiết ở khung Tiến trình và file log."
            if not duong_log:
                m = re.findall(r"\[log\] (.+)", self._log_chay)
                duong_log = m[-1].strip() if m else str(cau_hinh.thu_muc_logs())
            box = QtWidgets.QMessageBox(self)
            box.setIcon(QtWidgets.QMessageBox.Icon.Critical)
            box.setWindowTitle("Tách răng không thành công")
            box.setText(cau)
            box.setInformativeText(f"Mã lỗi {code}. Chi tiết kỹ thuật đã ghi vào:\n{duong_log}")
            nut_log = box.addButton("Mở thư mục log", QtWidgets.QMessageBox.ButtonRole.ActionRole)
            box.addButton(QtWidgets.QMessageBox.StandardButton.Ok)
            box.exec()
            if box.clickedButton() is nut_log:
                d = Path(duong_log)
                d = d if d.is_dir() else d.parent
                if d.is_dir():
                    os.startfile(str(d))  # noqa: S606

        def on_stop(self):
            if self.proc is not None:
                subprocess.call(["taskkill", "/F", "/T", "/PID",
                                 str(self.proc.processId())],
                                creationflags=CREATE_NO_WINDOW)
                self.log_write("\n[Đã dừng theo yêu cầu]\n")

        def on_open_out(self):
            out = self.out_edit.text().strip()
            if out and Path(out).is_dir():
                os.startfile(out)  # noqa: S606

        def on_edit(self):
            """Mở cửa sổ Xem & Sửa cho ca đang mở."""
            case = self._ca_hien
            if not case:
                QtWidgets.QMessageBox.information(
                    self, "Chưa có ca", "Ca đang mở chưa có kết quả tách.")
                return
            try:
                from tachrang.ui.xem_sua import mo_xem_sua
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Lỗi", f"Không mở được Xem & Sửa:\n{e}")
                return
            w = mo_xem_sua(Path(self.out_edit.text().strip()), case, self)
            if w is not None:
                if not hasattr(self, "_editors"):
                    self._editors = []
                self._editors.append(w)

        # ── Preview nhúng ─────────────────────────────────────────────────
        def refresh_cases(self, auto_render=False):
            """Tìm kết quả của CA ĐANG MỞ (theo DICOM đã chọn); nếu chưa nạp DICOM
            thì lấy ca mới xử lý xong nhất."""
            stl_root = Path(self.out_edit.text().strip() or ".") / "stl"
            cases = []
            if stl_root.is_dir():
                dirs = [d for d in stl_root.iterdir()
                        if d.is_dir() and any(d.glob("*.stl"))]
                cases = [d.name for d in
                         sorted(dirs, key=lambda d: d.stat().st_mtime, reverse=True)]
            if self._ct_case and self._ct_case in cases:
                case = self._ct_case
            elif cases and not self._ct_case:
                case = cases[0]
            else:
                case = ""
            if not case:
                self._ca_hien = ""
                self.lb_ca.setText("Chưa có kết quả cho ca đang mở")
                return
            if auto_render or case != self._ca_hien:
                self.render_case(case)

        def render_case(self, case):
            if not case:
                return
            self._ca_hien = case
            self.lb_ca.setText(f"Ca đang mở: <b>{case}</b>")
            if hasattr(self, "lb_ca_3s"):
                self.lb_ca_3s.setText(f"Ca CBCT: <b>{case}</b>")
            if hasattr(self, "_3s_actors"):
                for lop in self._3s_actors.values():
                    lop.clear()            # renderer sắp RemoveAllViewProps; bảng giữ, phải đối chiếu lại
                self._dc = None
            stl_dir = Path(self.out_edit.text().strip()) / "stl" / case
            self.renderer.RemoveAllViewProps()
            self._stl_actors = {}
            actors = []
            tooth_i = 0
            for f in sorted(Path(stl_dir).glob("*.stl")):
                if "_can-CBCT" in f.stem:
                    continue                      # scan đã căn: hiện riêng (màu xanh lơ)
                actor, tooth_i = actor_for_stl(f, tooth_i)
                actors.append(actor)
                self._stl_actors[khoa_ten(f.stem)] = actor
            if self.volume_actor is not None and case == self._ct_case:
                self.renderer.AddVolume(self.volume_actor)
                self.volume_actor.SetVisibility(self.cb_ct3d.isChecked())
            for a in actors:
                self.renderer.AddActor(a)
            # Scan hàm: nạp lại mọi bản đã căn của ca này; scan thô đang chờ căn chỉ giữ nếu cùng ca
            tho = [(p, d) for p, d in self._scan_items.items()
                   if not d["da_can"] and d.get("case") in (case, "", None)]
            self._scan_xoa_het()
            self._nap_scan_da_can(case)
            for p, d in tho:
                hien = d["item"].checkState() == QtCore.Qt.CheckState.Checked
                self._scan_them(p, da_can=False, hien=hien)
            if not tho:
                for ed in (self.scan_edit_tren, self.scan_edit_duoi):
                    if ed.text().strip():
                        ed.setText("")             # đường dẫn scan của ca khác
            self.hint.SetInput(f"{case} — {len(actors)} cau truc | "
                               "Chuot trai: xoay | Lan chuot: zoom | Giua: keo")
            self.renderer.AddActor2D(self.hint)
            self.nap_ket_qua(case)      # bản đồ nhãn + CT nền (nếu cần) + danh sách vùng
            self.renderer.ResetCamera()
            self.vtk_widget.GetRenderWindow().Render()
            self.statusBar().showMessage(f"{case}: {len(actors)} cấu trúc")

        # ── Sửa nhãn trực tiếp tại màn hình chính ─────────────────────────────
        def nap_ket_qua(self, case):
            """Nạp bản đồ nhãn của ca để xem màu + sửa ngay trên 3 lát cắt."""
            import SimpleITK as sitk
            n = self.nguon
            out = Path(self.out_edit.text().strip() or ".")
            lm = out / "labelmaps" / f"{case}.nii.gz"
            js = out / "labelmaps" / f"{case}.json"
            ct = out / "staged_inputs" / f"{case}.nii.gz"
            self.ds_vung.blockSignals(True)
            self.ds_vung.clear()
            self.ds_vung.blockSignals(False)
            self.lab = None
            n.lab = None
            self._case_edit = None
            self.undo_stack = []
            self._actors_nhan = {}
            self._cap_nhat_trang_thai_nhap()
            if not (lm.is_file() and js.is_file()):
                n.epoch += 1
                for cv in self.canvases:
                    cv.update()
                return
            try:
                self._lm_img = sitk.ReadImage(str(lm))
                lab = sitk.GetArrayFromImage(self._lm_img).astype(np.int16)
            except Exception as e:
                self.log_write(f"[Sửa] Không đọc được bản đồ nhãn: {e}\n")
                return
            # CT nền: nếu ca đang chọn khác ca DICOM đã nạp thì lấy CT đã chuẩn hóa
            if (n.ct_u8 is None or self._ct_case != case
                    or tuple(lab.shape) != tuple(n.shape)):
                if not ct.is_file():
                    return
                import tachrang.core.pipeline as pl
                img = sitk.ReadImage(str(ct))
                arr = sitk.GetArrayFromImage(img)
                n.ct_u8 = khung_xem.cua_so_u8(arr)
                n.sp = img.GetSpacing()
                n.shape = tuple(arr.shape)
                self._matrix = pl.physical_matrix(img)
                self._ct_case = case
                self._da_nap = None    # CT không còn ứng với ô thư mục DICOM
                for cv, sl in zip(self.canvases, self.sliders):
                    sl.blockSignals(True)
                    sl.setRange(0, n.shape[cv.axis] - 1)
                    cv.dat_lai()
                    sl.setValue(cv.k)
                    sl.blockSignals(False)
                self.volume_actor = khung_xem.tao_volume_ct(
                    n.ct_u8, self._matrix, nguong=float(self.sl_nguong.value()),
                    do_dam=self.sl_dam.value() / 100.0)
                self.renderer.AddVolume(self.volume_actor)
                self.volume_actor.SetVisibility(self.cb_ct3d.isChecked())
                self._scan_cap_nhat_lat()          # CT mới -> viền scan trên lát tính lại
            self.lab = lab
            n.lab = lab
            self._case_edit = case
            try:
                data = json.loads(js.read_text(encoding="utf-8"))
                self.names = {int(k): v for k, v in data.get("labels", {}).items()}
            except Exception:
                self.names = {}
            for i in np.unique(lab):
                if i > 0 and int(i) not in self.names:
                    self.names[int(i)] = f"label-{int(i)}"
            self._nap_ds_vung()
            self._lam_lut()
            self._gan_actor_nhan(case)
            n.epoch += 1
            for cv in self.canvases:
                cv.update()
            self._sua_dirty = False
            self._cap_nhat_trang_thai_nhap()
            # Có bản làm dở: chỉ BÁO cho biết — KHÔNG tự nạp, không bật hộp thoại.
            # Người dùng chủ động bấm "↻ Khôi phục bản làm dở" khi muốn mở lại.
            if self.btn_khoi_phuc.isEnabled():
                self.log_write(f"[Nháp] {self.lb_nhap.text()} — chưa nạp; "
                               "bấm '↻ Khôi phục bản làm dở' khi muốn mở lại.\n")
                self.statusBar().showMessage(
                    self.lb_nhap.text() + " — bấm '↻ Khôi phục bản làm dở' khi cần", 8000)

        def _nap_ds_vung(self):
            from tachrang.ui.xem_sua import mau_cho_nhan
            self.ds_vung.blockSignals(True)
            self.ds_vung.clear()
            for i in sorted(self.names):
                it = QtWidgets.QListWidgetItem(self.names[i])
                it.setData(QtCore.Qt.ItemDataRole.UserRole, int(i))
                it.setFlags(it.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable
                            | QtCore.Qt.ItemFlag.ItemIsEditable)
                it.setCheckState(QtCore.Qt.CheckState.Checked)
                px = QtGui.QPixmap(14, 14)
                px.fill(QtGui.QColor(*mau_cho_nhan(i, self.names[i])))
                it.setIcon(QtGui.QIcon(px))
                self.ds_vung.addItem(it)
            self.ds_vung.blockSignals(False)

        def _lam_lut(self):
            from tachrang.ui.xem_sua import mau_cho_nhan
            n = self.nguon
            mx = max(list(self.names) + [0]) + 2
            lut = np.zeros((mx, 3), np.uint8)
            for i, nm in self.names.items():
                lut[i] = mau_cho_nhan(i, nm)
            vis = np.ones(mx, bool)
            for r in range(self.ds_vung.count()):
                it = self.ds_vung.item(r)
                lid = it.data(QtCore.Qt.ItemDataRole.UserRole)
                if lid is not None and lid < mx:
                    vis[lid] = it.checkState() == QtCore.Qt.CheckState.Checked
            n.color_lut, n.vis_lut = lut, vis

        def _gan_actor_nhan(self, case):
            """Nối id nhãn với actor STL trong khung 3D (để tích = ẩn/hiện)
            và tô actor ĐÚNG MÀU của nhãn trên lát cắt (3D = 2D)."""
            from tachrang.ui.xem_sua import mau_cho_nhan, la_xuong
            self._actors_nhan = {}
            for i, nm in self.names.items():
                a = self._stl_actors.get(khoa_ten(f"{case}_{nm}"))
                if a is not None:
                    self._actors_nhan[i] = a
                    r, g, b = mau_cho_nhan(i, nm)
                    pr = a.GetProperty()
                    pr.SetColor(r / 255.0, g / 255.0, b / 255.0)
                    n_l = nm.lower()
                    if "sinus" in n_l or "xoang" in n_l:
                        pr.SetOpacity(0.50)
                    elif la_xuong(nm):
                        pr.SetOpacity(0.35)

        def _doi_item(self, it):
            i = it.data(QtCore.Qt.ItemDataRole.UserRole)
            if i is None or self.lab is None:
                return
            n = self.nguon
            on = it.checkState() == QtCore.Qt.CheckState.Checked
            if n.vis_lut is not None and i < len(n.vis_lut):
                n.vis_lut[i] = on
            ten = it.text().strip()
            if ten and ten != self.names.get(i):
                self.names[i] = ten
                self._sua_dirty = True
            a = self._actors_nhan.get(i)
            if a is not None:
                a.SetVisibility(on)
            n.epoch += 1
            for cv in self.canvases:
                cv.update()
            self.vtk_widget.GetRenderWindow().Render()

        def _tick_het(self, on):
            st = QtCore.Qt.CheckState.Checked if on else QtCore.Qt.CheckState.Unchecked
            self.ds_vung.blockSignals(True)
            for r in range(self.ds_vung.count()):
                self.ds_vung.item(r).setCheckState(st)
            self.ds_vung.blockSignals(False)
            n = self.nguon
            if n.vis_lut is not None:
                n.vis_lut[1:] = on
            for a in self._actors_nhan.values():
                a.SetVisibility(on)
            n.epoch += 1
            for cv in self.canvases:
                cv.update()
            self.vtk_widget.GetRenderWindow().Render()

        def _vung_moi(self):
            from tachrang.ui.xem_sua import mau_cho_nhan
            if self.lab is None:
                QtWidgets.QMessageBox.information(
                    self, "Chưa có ca", "Hãy tách một ca (kiểu KẾT HỢP) trước đã.")
                return
            i = max(list(self.names) + [200]) + 1
            self.names[i] = f"Vung-moi-{i - 200}"
            self.ds_vung.blockSignals(True)
            it = QtWidgets.QListWidgetItem(self.names[i])
            it.setData(QtCore.Qt.ItemDataRole.UserRole, int(i))
            it.setFlags(it.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable
                        | QtCore.Qt.ItemFlag.ItemIsEditable)
            it.setCheckState(QtCore.Qt.CheckState.Checked)
            px = QtGui.QPixmap(14, 14)
            px.fill(QtGui.QColor(*mau_cho_nhan(i, self.names[i])))
            it.setIcon(QtGui.QIcon(px))
            self.ds_vung.addItem(it)
            self.ds_vung.blockSignals(False)
            self.ds_vung.setCurrentItem(it)
            self._lam_lut()
            self.rb_to.setChecked(True)
            self.statusBar().showMessage(
                f"Đã thêm '{self.names[i]}' — bôi chuột trái lên lát cắt để vẽ")

        # giao thức tô vẽ cho NguonSua
        def _nhan_dang_chon(self):
            it = self.ds_vung.currentItem()
            return None if it is None else it.data(QtCore.Qt.ItemDataRole.UserRole)

        def _lay_lat(self, axis, k):
            if axis == 0:
                return self.lab[k]
            if axis == 1:
                return self.lab[:, k]
            return self.lab[:, :, k]

        def bat_dau_net_ve(self, axis, k):
            if self.lab is None:
                return
            self._net = []
            self.undo_stack.append({"nhan": set(), "net": self._net, "names": None})
            if len(self.undo_stack) > 20:
                self.undo_stack.pop(0)

        def to_tai(self, axis, k, r, c):
            """Bút CẦU 3D: mỗi lần chấm ăn cả khối cầu bán kính 'bút mm'
            (nhiều lát liền nhau) — tô chỉ vào chỗ trống, xóa chỉ vùng mình."""
            i = self._nhan_dang_chon()
            if i is None or self.lab is None:
                return
            n = self.nguon
            sp = n.sp                      # (sx, sy, sz)
            spz, spy, spx = sp[2], sp[1], sp[0]
            cz, cy, cx = {0: (k, r, c), 1: (r, k, c), 2: (r, c, k)}[axis]
            mm = float(self.spin_but.value())
            rz = max(mm / max(spz, 1e-6), 0.0)
            ry = max(mm / max(spy, 1e-6), 0.6)
            rx = max(mm / max(spx, 1e-6), 0.6)
            z0, z1 = int(max(cz - rz, 0)), int(min(cz + rz + 1, self.lab.shape[0]))
            y0, y1 = int(max(cy - ry, 0)), int(min(cy + ry + 1, self.lab.shape[1]))
            x0, x1 = int(max(cx - rx, 0)), int(min(cx + rx + 1, self.lab.shape[2]))
            if z0 >= z1 or y0 >= y1 or x0 >= x1:
                return
            bb = (slice(z0, z1), slice(y0, y1), slice(x0, x1))
            zz, yy, xx = np.ogrid[z0:z1, y0:y1, x0:x1]
            ball = (((zz - cz) / max(rz, 1e-6)) ** 2
                    + ((yy - cy) / max(ry, 1e-6)) ** 2
                    + ((xx - cx) / max(rx, 1e-6)) ** 2) <= 1.0
            sub = self.lab[bb]
            if self._net is not None:
                self._net.append((bb, sub.copy()))
                if self.undo_stack:
                    self.undo_stack[-1]["nhan"].add(int(i))
            if self.rb_to.isChecked():
                chon = ball
                if self.cb_bam_sang.isChecked() and n.ct_u8 is not None:
                    chon = ball & (n.ct_u8[bb] >= self.sl_nguong.value())
                    # chỉ lấy phần LIỀN KHỐI với điểm bấm: khe tối giữa 2 răng
                    # chặn màu lan sang răng bên cạnh -> tô chuẩn từng răng
                    if chon.any():
                        from scipy import ndimage as ndi
                        nhom, _ = ndi.label(chon, np.ones((3, 3, 3), bool))
                        tam = (int(cz) - z0, int(cy) - y0, int(cx) - x0)
                        g_tam = nhom[tam] if all(
                            0 <= tam[a] < nhom.shape[a] for a in range(3)) else 0
                        if g_tam > 0:
                            chon = nhom == g_tam
                        else:
                            chon[:] = False    # bấm vào chỗ tối: không tô gì
                sub[chon] = i
            else:
                sub[ball & (sub == i)] = 0
            self._nhan_sua = int(i)
            self._sua_dirty = True
            n.epoch += 1
            for cv in self.canvases:
                cv.update()

        def ket_thuc_net_ve(self):
            """Nhả chuột: dựng lại bề mặt 3D của vùng vừa tô/xóa."""
            i, self._nhan_sua, self._net = self._nhan_sua, None, None
            if i is not None:
                self._cap_nhat_3d_nhan(i)

        def hoan_tac(self):
            if not self.undo_stack or self.lab is None:
                return
            buoc = self.undo_stack.pop()
            for bb, patch in reversed(buoc["net"]):
                self.lab[bb] = patch
            if buoc["names"] is not None:
                self.names = buoc["names"]
                self._nap_ds_vung()
                self._lam_lut()
            self.nguon.epoch += 1
            for cv in self.canvases:
                cv.update()
            for i in buoc["nhan"]:
                self._cap_nhat_3d_nhan(i, render=False)
            self.vtk_widget.GetRenderWindow().Render()

        def _cap_nhat_3d_nhan(self, i, render=True):
            """Dựng lại bề mặt 3D của vùng i từ bản đồ nhãn (không cần xuất STL)."""
            if self.lab is None or self._matrix is None or i is None:
                return
            from scipy import ndimage
            import tachrang.core.pipeline as pl
            from tachrang.ui.xem_sua import mau_cho_nhan, la_xuong
            mask = self.lab == i
            slcs = ndimage.find_objects(mask.astype(np.int8))
            a = self._actors_nhan.get(i)
            if not slcs or slcs[0] is None:
                if a is not None:
                    a.SetVisibility(False)
                if render:
                    self.vtk_widget.GetRenderWindow().Render()
                return
            slc = slcs[0]
            pad = 4
            z0 = max(slc[0].start - pad, 0); z1 = min(slc[0].stop + pad, mask.shape[0])
            y0 = max(slc[1].start - pad, 0); y1 = min(slc[1].stop + pad, mask.shape[1])
            x0 = max(slc[2].start - pad, 0); x1 = min(slc[2].stop + pad, mask.shape[2])
            crop = np.ascontiguousarray(mask[z0:z1, y0:y1, x0:x1])
            poly = pl.mask_to_polydata(crop, (float(x0), float(y0), float(z0)),
                                       self._matrix, 10, 0.01, 0.0)
            nm = self.names.get(i, "")
            if a is None:
                mp = vtk.vtkPolyDataMapper()
                a = vtk.vtkActor()
                a.SetMapper(mp)
                pr = a.GetProperty()
                r, g, b = mau_cho_nhan(i, nm)
                pr.SetColor(r / 255.0, g / 255.0, b / 255.0)
                n_l = nm.lower()
                if "sinus" in n_l or "xoang" in n_l:
                    pr.SetOpacity(0.50)
                elif la_xuong(nm):
                    pr.SetOpacity(0.35)
                pr.SetSpecular(0.25)
                pr.SetSpecularPower(20)
                self.renderer.AddActor(a)
                self._actors_nhan[i] = a
            a.GetMapper().SetInputData(poly)
            n = self.nguon
            hien = True
            if n.vis_lut is not None and i < len(n.vis_lut):
                hien = bool(n.vis_lut[i])
            a.SetVisibility(hien)
            if render:
                self.vtk_widget.GetRenderWindow().Render()

        def _bam_nhan(self, i):
            """Bấm vào một răng trên lát cắt (chế độ Xem) -> chọn dòng tương ứng."""
            if i <= 0 or self.lab is None:
                return
            for r in range(self.ds_vung.count()):
                it = self.ds_vung.item(r)
                if it.data(QtCore.Qt.ItemDataRole.UserRole) == i:
                    self._bo_qua_nhay = True
                    self.ds_vung.setCurrentRow(r)
                    self._bo_qua_nhay = False
                    self.statusBar().showMessage(
                        f"Đã chọn: {self.names.get(i, i)} — Tô/Xóa sẽ tác động vùng này")
                    break

        def _nhay_den_vung(self, it, _=None):
            """Chọn một dòng trong danh sách -> 3 lát cắt nhảy đến giữa vùng đó."""
            if it is None or self.lab is None or self._bo_qua_nhay:
                return
            i = it.data(QtCore.Qt.ItemDataRole.UserRole)
            if i is None:
                return
            from scipy import ndimage
            slcs = ndimage.find_objects((self.lab == i).astype(np.int8))
            if not slcs or slcs[0] is None:
                return
            slc = slcs[0]
            tam = [int((s.start + s.stop) // 2) for s in slc]
            for cv in self.canvases:
                cv.set_k(tam[cv.axis])
            self.statusBar().showMessage(
                f"{self.names.get(i, i)} — đã đưa 3 lát cắt đến giữa vùng")

        def _gop_vung(self):
            """Gộp vùng đang chọn vào một vùng khác (nhanh hơn tô tay)."""
            src = self._nhan_dang_chon()
            if src is None or self.lab is None:
                QtWidgets.QMessageBox.information(
                    self, "Chọn vùng", "Hãy chọn vùng cần gộp trong danh sách trước.")
                return
            khac = [(j, nm) for j, nm in sorted(self.names.items()) if j != src]
            if not khac:
                return
            ten_src = self.names.get(src, str(src))
            # Xếp ứng viên THÔNG MINH: vùng chạm nhiều nhất lên đầu, rồi đến gần nhất
            from scipy import ndimage
            mask_s = self.lab == src
            slcs = ndimage.find_objects(mask_s.astype(np.int8))
            cham = {}
            tam_s = None
            if slcs and slcs[0] is not None:
                pad = 2
                slc = slcs[0]
                z0 = max(slc[0].start - pad, 0); z1 = min(slc[0].stop + pad, self.lab.shape[0])
                y0 = max(slc[1].start - pad, 0); y1 = min(slc[1].stop + pad, self.lab.shape[1])
                x0 = max(slc[2].start - pad, 0); x1 = min(slc[2].stop + pad, self.lab.shape[2])
                vung_s = mask_s[z0:z1, y0:y1, x0:x1]
                lan = ndimage.binary_dilation(vung_s, np.ones((3, 3, 3), bool), 2)
                vien = self.lab[z0:z1, y0:y1, x0:x1][lan & ~vung_s]
                bc = np.bincount(vien[vien > 0])
                cham = {int(l): int(c) for l, c in enumerate(bc) if c > 0 and l != src}
                w = np.where(mask_s)
                tam_s = np.array([v.mean() for v in w])
            def khoang_cach(j):
                if tam_s is None:
                    return 1e9
                sl = ndimage.find_objects((self.lab == j).astype(np.int8))
                if not sl or sl[0] is None:
                    return 1e9
                t = np.array([(s.start + s.stop) / 2 for s in sl[0]])
                return float(np.linalg.norm(t - tam_s))
            khac.sort(key=lambda cap: (-cham.get(cap[0], 0), khoang_cach(cap[0])))
            items = []
            for j, nm in khac:
                if cham.get(j):
                    items.append(f"{nm}   — đang chạm vùng này ⭐")
                else:
                    items.append(nm)
            chon, ok = QtWidgets.QInputDialog.getItem(
                self, "Gộp vùng", f"Gộp '{ten_src}' vào vùng:\n"
                "(vùng đang chạm được xếp lên đầu)", items, 0, False)
            if not ok or not chon:
                return
            dst = khac[items.index(chon)][0]
            from scipy import ndimage
            mask = self.lab == src
            slcs = ndimage.find_objects(mask.astype(np.int8))
            net = []
            if slcs and slcs[0] is not None:
                bb = slcs[0]
                net.append((bb, self.lab[bb].copy()))
            self.undo_stack.append({"nhan": {int(src), int(dst)}, "net": net,
                                    "names": dict(self.names)})
            if len(self.undo_stack) > 20:
                self.undo_stack.pop(0)
            self.lab[mask] = np.int16(dst)
            self.names.pop(src, None)
            a = self._actors_nhan.pop(src, None)
            if a is not None:
                self.renderer.RemoveActor(a)
            self._nap_ds_vung()
            self._lam_lut()
            for r in range(self.ds_vung.count()):
                if self.ds_vung.item(r).data(QtCore.Qt.ItemDataRole.UserRole) == dst:
                    self.ds_vung.setCurrentRow(r)
                    break
            self._sua_dirty = True
            self.nguon.epoch += 1
            for cv in self.canvases:
                cv.update()
            self._cap_nhat_3d_nhan(dst)
            self.statusBar().showMessage(
                f"Đã gộp '{ten_src}' vào '{self.names.get(dst, dst)}' — Ctrl+Z để hoàn tác")

        # ── Công cụ thông minh (ngưỡng / làm mịn / mọc từ hạt) ────────────────
        def _hoi_tham_so(self, tieu_de, mo_ta, truong):
            """Hộp thoại 1 lần cho vài tham số. truong = [(khóa, nhãn, widget)].
            Trả về dict khóa->giá trị hoặc None nếu hủy."""
            dlg = QtWidgets.QDialog(self)
            dlg.setWindowTitle(tieu_de)
            lay = QtWidgets.QVBoxLayout(dlg)
            lb = QtWidgets.QLabel(mo_ta)
            lb.setWordWrap(True)
            lay.addWidget(lb)
            form = QtWidgets.QFormLayout()
            for _, nhan, w in truong:
                form.addRow(nhan, w)
            lay.addLayout(form)
            nut = QtWidgets.QDialogButtonBox(
                QtWidgets.QDialogButtonBox.StandardButton.Ok
                | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
            nut.accepted.connect(dlg.accept)
            nut.rejected.connect(dlg.reject)
            lay.addWidget(nut)
            if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
                return None
            ket = {}
            for khoa, _, w in truong:
                if isinstance(w, QtWidgets.QComboBox):
                    ket[khoa] = w.currentIndex()
                elif isinstance(w, QtWidgets.QCheckBox):
                    ket[khoa] = w.isChecked()
                else:
                    ket[khoa] = w.value()
            return ket

        def _spin_mm(self, gia_tri, lo, hi, buoc=0.5):
            s = QtWidgets.QDoubleSpinBox()
            s.setRange(lo, hi)
            s.setSingleStep(buoc)
            s.setDecimals(1)
            s.setSuffix(" mm")
            s.setValue(gia_tri)
            return s

        def _ap_ket_qua_sua(self, kq, ten):
            """Đưa KetQua của sua_nhan vào Hoàn tác + vẽ lại 2D/3D."""
            if not kq.net:
                self.statusBar().showMessage(f"{ten}: không thay đổi ({kq.ghi_chu})")
                return False
            self.undo_stack.append({"nhan": set(kq.nhan), "net": kq.net, "names": None})
            if len(self.undo_stack) > 20:
                self.undo_stack.pop(0)
            self._sua_dirty = True
            self.nguon.epoch += 1
            for cv in self.canvases:
                cv.update()
            for i in kq.nhan:
                self._cap_nhat_3d_nhan(i, render=False)
            self.vtk_widget.GetRenderWindow().Render()
            self.statusBar().showMessage(f"{ten}: {kq.ghi_chu} — Ctrl+Z để hoàn tác")
            self.log_write(f"[Sửa] {ten}: {kq.ghi_chu}\n")
            return True

        def _can_vung_chon(self, ten):
            i = self._nhan_dang_chon()
            if self.lab is None:
                QtWidgets.QMessageBox.information(
                    self, ten, "Chưa có bản đồ nhãn — hãy tách một ca (kiểu KẾT HỢP) trước.")
                return None
            if i is None:
                QtWidgets.QMessageBox.information(
                    self, ten, "Hãy chọn một vùng trong danh sách trước.")
                return None
            return int(i)

        def _lap_nguong(self):
            ten = "Lấp theo ngưỡng"
            i = self._can_vung_chon(ten)
            if i is None:
                return
            nm = self.names.get(i, str(i))
            sp_r = self._spin_mm(3.0, 0.5, 30.0)
            sp_ng = QtWidgets.QSpinBox()
            sp_ng.setRange(1, 254)
            sp_ng.setValue(int(self.sl_nguong.value()))
            ts = self._hoi_tham_so(
                ten, f"Thêm vào '<b>{nm}</b>' mọi điểm sáng ≥ ngưỡng, chưa có nhãn, "
                     "liền khối với vùng và cách vùng không quá bán kính.",
                [("r", "Bán kính lan tối đa", sp_r),
                 ("ng", "Ngưỡng sáng (0-255)", sp_ng)])
            if ts is None:
                return
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
            try:
                kq = sua_nhan.lap_theo_nguong(self.lab, self.nguon.ct_u8, i, ts["ng"],
                                              ts["r"], self.nguon.sp)
            finally:
                QtWidgets.QApplication.restoreOverrideCursor()
            self._ap_ket_qua_sua(kq, f"{ten} '{nm}'")

        def _lam_min(self):
            ten = "Làm mịn vùng"
            i = self._can_vung_chon(ten)
            if i is None:
                return
            nm = self.names.get(i, str(i))
            sp_s = self._spin_mm(0.4, 0.1, 3.0, 0.1)
            cb = QtWidgets.QCheckBox("Cho phép lấn sang vùng khác")
            ts = self._hoi_tham_so(
                ten, f"Làm mượt bề mặt '<b>{nm}</b>' (Gaussian, ngưỡng 0.5). "
                     "Độ mịn lớn xóa nhiều chi tiết nhỏ hơn.",
                [("s", "Độ mịn (sigma)", sp_s), ("de", "", cb)])
            if ts is None:
                return
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
            try:
                kq = sua_nhan.lam_min_vung(self.lab, i, ts["s"], self.nguon.sp, de_len=ts["de"])
            finally:
                QtWidgets.QApplication.restoreOverrideCursor()
            self._ap_ket_qua_sua(kq, f"{ten} '{nm}'")

        def _moc_tu_hat(self):
            ten = "Mọc từ hạt"
            if self.lab is None:
                QtWidgets.QMessageBox.information(
                    self, ten, "Chưa có bản đồ nhãn — hãy tách một ca (kiểu KẾT HỢP) trước.")
                return
            from tachrang.ui.xem_sua import la_xuong
            sp_r = self._spin_mm(3.0, 0.5, 20.0)
            sp_ng = QtWidgets.QSpinBox()
            sp_ng.setRange(1, 254)
            sp_ng.setValue(int(self.sl_nguong.value()))
            pham_vi = QtWidgets.QComboBox()
            pham_vi.addItems(["Chỉ các răng (xương không mọc)",
                              "Chỉ vùng đang chọn",
                              "Tất cả vùng đã có"])
            ts = self._hoi_tham_so(
                ten, "Mọi chỗ sáng chưa có nhãn, chạm vào vùng đã có và trong bán kính "
                     "sẽ nhận nhãn của vùng GẦN NHẤT. Dùng để phủ nhanh phần AI còn thiếu.",
                [("r", "Bán kính lan tối đa", sp_r),
                 ("ng", "Ngưỡng sáng (0-255)", sp_ng),
                 ("pv", "Phạm vi", pham_vi)])
            if ts is None:
                return
            chi_nhan, bo_nhan = None, ()
            if ts["pv"] == 0:
                bo_nhan = tuple(i for i, nm in self.names.items()
                                if la_xuong(nm) or "canal" in nm.lower()
                                or "xoang" in nm.lower() or "sinus" in nm.lower())
            elif ts["pv"] == 1:
                i = self._nhan_dang_chon()
                if i is None:
                    QtWidgets.QMessageBox.information(self, ten, "Hãy chọn một vùng trước.")
                    return
                chi_nhan = [int(i)]
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
            try:
                kq = sua_nhan.moc_tu_hat(self.lab, self.nguon.ct_u8, ts["ng"], ts["r"],
                                         self.nguon.sp, chi_nhan=chi_nhan, bo_nhan=bo_nhan)
            finally:
                QtWidgets.QApplication.restoreOverrideCursor()
            self._ap_ket_qua_sua(kq, ten)

        # ── Đo khoảng cách / góc ──────────────────────────────────────────────
        def _do_xong(self, d):
            ten = "Khoảng cách" if d["kieu"] == "kc" else "Góc"
            truc = khung_xem.TEN_TRUC[d["axis"]]
            self.lb_do.setText(f"{ten}: {d['chu']}")
            self.statusBar().showMessage(f"{ten} = {d['chu']} ({truc}, lát {d['k'] + 1})")
            self.log_write(f"[Đo] {ten} = {d['chu']} — {truc}, lát {d['k'] + 1}\n")

        def _xoa_do(self):
            self.nguon.do_dac = []
            self.lb_do.setText("")
            for cv in self.canvases:
                cv.update()
            self.statusBar().showMessage("Đã xóa mọi số đo")

        def luu_nhan(self):
            """Ghi bản đồ nhãn + tên vùng đã sửa xuống đĩa."""
            if self.lab is None or self._case_edit is None:
                return False
            import SimpleITK as sitk
            out = Path(self.out_edit.text().strip() or ".")
            lm = out / "labelmaps" / f"{self._case_edit}.nii.gz"
            js = out / "labelmaps" / f"{self._case_edit}.json"
            img = sitk.GetImageFromArray(self.lab)
            if self._lm_img is not None:
                img.CopyInformation(self._lm_img)
            sitk.WriteImage(img, str(lm), useCompression=True)
            js.write_text(json.dumps(
                {"case": self._case_edit,
                 "labels": {str(k): v for k, v in sorted(self.names.items())}},
                ensure_ascii=False, indent=1), encoding="utf-8")
            self._sua_dirty = False
            self.log_write(f"[Sửa] Đã lưu chỉnh sửa: {lm.name}\n")
            self.statusBar().showMessage("Đã lưu chỉnh sửa")
            # Kết quả gốc đã cập nhật -> bản nháp cũ không còn ý nghĩa
            for f in self._duong_nhap():
                try:
                    f.unlink()
                except OSError:
                    pass
            self._cap_nhat_trang_thai_nhap()
            return True

        # ── Bản LÀM DỞ (nháp) — lưu riêng, không đè kết quả gốc ──────────────
        def _duong_nhap(self, case=None):
            case = case or self._case_edit
            out = Path(self.out_edit.text().strip() or ".")
            return (out / "labelmaps" / f"{case}.lam-do.nii.gz",
                    out / "labelmaps" / f"{case}.lam-do.json")

        def _cap_nhat_trang_thai_nhap(self):
            """Bật/tắt nút Khôi phục + dòng thông tin theo file nháp hiện có."""
            if self._case_edit is None:
                self.btn_khoi_phuc.setEnabled(False)
                self.lb_nhap.setText("")
                return
            lm, js = self._duong_nhap()
            co = lm.is_file() and js.is_file()
            self.btn_khoi_phuc.setEnabled(co)
            if co:
                try:
                    t = json.loads(js.read_text(encoding="utf-8")).get("thoi_gian", "")
                except Exception:
                    t = ""
                self.lb_nhap.setText(f"Có bản làm dở lưu lúc {t}" if t
                                     else "Có bản làm dở đã lưu")
            else:
                self.lb_nhap.setText("")

        def luu_nhap(self, tu_dong=False):
            """Lưu tình trạng đang sửa (nhãn + tên + ô tích) vào file nháp riêng.

            - Tự lưu CHỈ ghi khi có thay đổi mới kể từ lần lưu trước
              (không ghi lại file lớn vô ích mỗi 3 phút).
            - Ghi NGUYÊN TỬ: ghi ra file tạm rồi đổi tên, nên bản nháp cũ
              không bao giờ hỏng dù tắt máy/mất điện giữa chừng."""
            if self.lab is None or self._case_edit is None:
                if not tu_dong:
                    QtWidgets.QMessageBox.information(
                        self, "Chưa có ca", "Chưa có ca nào đang mở để lưu.")
                return False
            if tu_dong and not self._sua_dirty:
                return False
            import datetime
            import SimpleITK as sitk
            lm, js = self._duong_nhap()
            lm.parent.mkdir(parents=True, exist_ok=True)
            # tên tạm giữ đuôi .nii.gz để SimpleITK nhận đúng định dạng
            lm_tam = lm.with_name(lm.name.replace(".lam-do.", ".lam-do.tam."))
            js_tam = js.with_name(js.name + ".tam")
            for f in (lm_tam, js_tam):          # dọn tàn dư nếu lần trước bị ngắt
                f.unlink(missing_ok=True)
            img = sitk.GetImageFromArray(self.lab)
            if self._lm_img is not None:
                img.CopyInformation(self._lm_img)
            sitk.WriteImage(img, str(lm_tam), useCompression=True)
            tick = {}
            for r in range(self.ds_vung.count()):
                it = self.ds_vung.item(r)
                tick[str(it.data(QtCore.Qt.ItemDataRole.UserRole))] = (
                    it.checkState() == QtCore.Qt.CheckState.Checked)
            t = datetime.datetime.now().strftime("%H:%M %d/%m/%Y")
            js_tam.write_text(json.dumps(
                {"case": self._case_edit, "thoi_gian": t,
                 "shape": [int(x) for x in self.lab.shape],
                 "labels": {str(k): v for k, v in sorted(self.names.items())},
                 "tick": tick},
                ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(lm_tam, lm)
            os.replace(js_tam, js)
            self._sua_dirty = False    # trạng thái hiện tại đã nằm an toàn trong nháp
            self._cap_nhat_trang_thai_nhap()
            self.log_write(f"[Nháp] Đã lưu bản làm dở lúc {t}"
                           f"{' (tự động)' if tu_dong else ''}\n")
            self.statusBar().showMessage(f"Đã lưu bản làm dở lúc {t}")
            return True

        def khoi_phuc_nhap(self, hoi=True):
            """Mở lại bản nháp của ca đang mở; cập nhật 3D các vùng có thay đổi.
            KHÔNG bao giờ được gọi tự động — chỉ chạy khi người dùng bấm nút."""
            if self.lab is None or self._case_edit is None:
                return False
            import SimpleITK as sitk
            lm, js = self._duong_nhap()
            if not (lm.is_file() and js.is_file()):
                return False
            try:
                data = json.loads(js.read_text(encoding="utf-8"))
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Lỗi", f"Không đọc được bản nháp:\n{e}")
                return False
            # kiểm tra nhanh bằng metadata TRƯỚC khi đọc file nhãn lớn
            if data.get("case") not in (None, self._case_edit):
                QtWidgets.QMessageBox.warning(
                    self, "Không khớp", "Bản nháp thuộc ca khác — không nạp.")
                return False
            if "shape" in data and tuple(data["shape"]) != tuple(self.lab.shape):
                QtWidgets.QMessageBox.warning(
                    self, "Không khớp", "Bản nháp có kích thước khác kết quả hiện tại.")
                return False
            if hoi:
                tra_loi = QtWidgets.QMessageBox.question(
                    self, "Khôi phục bản làm dở",
                    f"Mở lại bản làm dở lưu lúc {data.get('thoi_gian', '?')}?\n"
                    "Những gì đang sửa chưa lưu sẽ bị thay bằng bản nháp.",
                    QtWidgets.QMessageBox.StandardButton.Yes
                    | QtWidgets.QMessageBox.StandardButton.No)
                if tra_loi != QtWidgets.QMessageBox.StandardButton.Yes:
                    return False
            try:
                lab_nhap = sitk.GetArrayFromImage(sitk.ReadImage(str(lm))).astype(np.int16)
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Lỗi", f"Không đọc được bản nháp:\n{e}")
                return False
            if tuple(lab_nhap.shape) != tuple(self.lab.shape):
                QtWidgets.QMessageBox.warning(
                    self, "Không khớp", "Bản nháp có kích thước khác kết quả hiện tại.")
                return False
            self._ap_dung_nhan(lab_nhap, data, "[Nháp] Đã khôi phục bản làm dở")
            self._sua_dirty = False        # trạng thái đang mở = bản nháp trên đĩa
            self.statusBar().showMessage("Đã khôi phục bản làm dở")
            return True

        def mo_file_nhan(self, duong=None):
            """Nạp file nhãn .nii.gz đã lưu trước (bất kỳ tên) để chỉnh tiếp.
            duong=None -> hỏi bằng hộp thoại; có sẵn (kéo-thả) -> nạp thẳng."""
            if self.lab is None or self._case_edit is None:
                QtWidgets.QMessageBox.information(
                    self, "Chưa có ca", "Hãy mở một ca có kết quả tách trước, rồi nạp file nhãn.")
                return False
            if not duong or isinstance(duong, bool):   # nút bấm truyền checked=False
                out = Path(self.out_edit.text().strip() or ".")
                bat_dau = str(self.settings.value("thu_muc_nhan", str(out / "labelmaps")))
                duong, _ = QtWidgets.QFileDialog.getOpenFileName(
                    self, "Mở file nhãn đã lưu", bat_dau,
                    "Bản đồ nhãn (*.nii.gz *.nii);;Tất cả (*)")
                if not duong:
                    return False
                self.settings.setValue("thu_muc_nhan", str(Path(duong).parent))
            duong = str(duong)
            import SimpleITK as sitk
            try:
                lab_moi = sitk.GetArrayFromImage(sitk.ReadImage(duong)).astype(np.int16)
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Lỗi", f"Không đọc được file:\n{e}")
                return False
            if tuple(lab_moi.shape) != tuple(self.lab.shape):
                QtWidgets.QMessageBox.warning(
                    self, "Không khớp",
                    f"File này có kích thước {lab_moi.shape[::-1]} khác ca đang mở "
                    f"{self.lab.shape[::-1]}.\nChỉ nạp đưủc file nhãn của cùng ca CBCT này.")
                return False
            # json cùng tên (bỏ .nii.gz/.nii) nếu có; không có thì giữ tên hiện tại
            p = Path(duong)
            goc = p.name[:-7] if p.name.endswith(".nii.gz") else p.stem
            js = p.parent / f"{goc}.json"
            data = {"labels": {str(k): v for k, v in self.names.items()}}
            if js.is_file():
                try:
                    data = json.loads(js.read_text(encoding="utf-8"))
                except Exception:
                    pass
            if self._sua_dirty:
                tra_loi = QtWidgets.QMessageBox.question(
                    self, "Nạp file nhãn",
                    "Những gì đang sửa chưa lưu sẽ bị thay bằng file này. Tiếp tục?",
                    QtWidgets.QMessageBox.StandardButton.Yes
                    | QtWidgets.QMessageBox.StandardButton.No)
                if tra_loi != QtWidgets.QMessageBox.StandardButton.Yes:
                    return False
            self._ap_dung_nhan(lab_moi, data, f"[Nạp] Đã nạp file nhãn {p.name}")
            self.statusBar().showMessage(f"Đã nạp {p.name} — bấm 'Lưu sửa' để ghi vào kết quả ca")
            return True

        def _ap_dung_nhan(self, lab_nhap, data, ghi_chu):
            """Thay bản đồ nhãn đang sửa bằng lab_nhap (+ tên, ô tích), dựng lại 3D
            CHỈ những vùng có thay đổi so với hiện tại."""
            # Các nhãn khác biệt -> cần dựng lại 3D
            khac = lab_nhap != self.lab
            doi = set(int(v) for v in np.unique(self.lab[khac])) | \
                set(int(v) for v in np.unique(lab_nhap[khac]))
            doi.discard(0)
            self.lab = lab_nhap
            self.nguon.lab = lab_nhap
            self.names = {int(k): v for k, v in data.get("labels", {}).items()}
            for i in np.unique(lab_nhap):
                if i > 0 and int(i) not in self.names:
                    self.names[int(i)] = f"label-{int(i)}"
            self.undo_stack = []
            self._nap_ds_vung()
            tick = data.get("tick", {})
            self.ds_vung.blockSignals(True)
            for r in range(self.ds_vung.count()):
                it = self.ds_vung.item(r)
                lid = str(it.data(QtCore.Qt.ItemDataRole.UserRole))
                if lid in tick:
                    it.setCheckState(QtCore.Qt.CheckState.Checked if tick[lid]
                                     else QtCore.Qt.CheckState.Unchecked)
            self.ds_vung.blockSignals(False)
            self._lam_lut()
            cu = dict(self._actors_nhan)
            self._gan_actor_nhan(self._case_edit)      # actor từ STL trên đĩa
            for i, a in cu.items():
                if self._actors_nhan.get(i) is a:
                    continue
                if i in self.names and i not in doi and i not in self._actors_nhan:
                    self._actors_nhan[i] = a           # vùng tự dựng, không đổi: giữ
                else:
                    self.renderer.RemoveActor(a)       # nhãn đã gộp/xóa hoặc sẽ dựng lại
            for i in sorted(doi):
                if i in self.names:
                    self._cap_nhat_3d_nhan(i, render=False)
            for i, a in self._actors_nhan.items():
                a.SetVisibility(bool(self.nguon.vis_lut[i])
                                if i < len(self.nguon.vis_lut) else True)
            self._sua_dirty = True
            self.nguon.epoch += 1
            for cv in self.canvases:
                cv.update()
            self.vtk_widget.GetRenderWindow().Render()
            self.log_write(f"{ghi_chu} ({len(doi)} vùng thay đổi)\n")

        def xuat_stl_sua(self):
            """Xuất STL các vùng đang tích, ngay tại màn hình chính."""
            if self.lab is None or self._case_edit is None:
                QtWidgets.QMessageBox.information(
                    self, "Chưa có ca", "Chưa có ca nào được tách (kiểu KẾT HỢP) để xuất.")
                return
            ids = [self.ds_vung.item(r).data(QtCore.Qt.ItemDataRole.UserRole)
                   for r in range(self.ds_vung.count())
                   if self.ds_vung.item(r).checkState() == QtCore.Qt.CheckState.Checked]
            if not ids:
                QtWidgets.QMessageBox.information(
                    self, "Chưa chọn vùng", "Hãy tích ít nhất một vùng để xuất.")
                return
            import tachrang.core.pipeline as pl
            self.luu_nhan()
            case = self._case_edit
            stl_dir = Path(self.out_edit.text().strip()) / "stl" / case
            stl_dir.mkdir(parents=True, exist_ok=True)
            self.statusBar().showMessage("Đang xuất STL...")
            QtWidgets.QApplication.processEvents()
            n_ok = 0
            for i in ids:
                nm = self.names.get(i, f"label-{i}")
                res = pl.export_labeled_mask(
                    self.lab == i, self._matrix,
                    stl_dir / f"{case}_{pl.sanitize(nm)}.stl", 30, 15, 0.01, 0.0)
                if res:
                    n_ok += 1
            self.render_case(case)     # nạp lại khung 3D theo file STL mới
            QtWidgets.QMessageBox.information(
                self, "Xuất xong",
                f"Đã xuất {n_ok} vùng vào:\n{stl_dir}")

        def closeEvent(self, event):
            # Đang sửa dở chưa lưu -> tự lưu bản nháp để lần sau mở lại
            if self.lab is not None and self._case_edit is not None and self._sua_dirty:
                try:
                    self.luu_nhap(tu_dong=True)
                except Exception:
                    pass
            self._luu_du_an_tu_dong()      # ghi lại dự án (kèm đường dẫn scan mới nhất)
            if self._loader is not None and self._loader.isRunning():
                self._loader.wait(10000)
            if self.proc is not None:
                subprocess.call(["taskkill", "/F", "/T", "/PID",
                                 str(self.proc.processId())],
                                creationflags=CREATE_NO_WINDOW)
            self.vtk_widget.GetRenderWindow().Finalize()
            event.accept()

    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE.replace("__CHECK__", _tao_anh_tick()))
    # Tránh Qt biến các khung lát cắt thành cửa sổ "native" khi đứng cạnh khung
    # VTK — nguyên nhân vẽ sai/đen khi phóng to thu nhỏ hay cuộn chuột
    QtCore.QCoreApplication.setAttribute(
        QtCore.Qt.ApplicationAttribute.AA_DontCreateNativeWidgetSiblings, True)
    log_file = nhat_ky.bat_dau_log("giao_dien")
    # Mọi thông báo của VTK (và thư viện C++ khác bị VTK bắt khi chạy pythonw) ghi vào
    # file log thay vì bật cửa sổ "vtkOutputWindow" làm người dùng hoảng
    _vtk_log = vtk.vtkFileOutputWindow()
    _vtk_log.SetFileName(str(cau_hinh.thu_muc_logs() / "vtk_output.log"))
    _vtk_log.SetAppend(True)
    vtk.vtkOutputWindow.SetInstance(_vtk_log)

    def _loi_chua_bat(kieu, gia_tri, tb):
        """Lỗi bất ngờ trong giao diện: ghi log + hộp thoại dễ hiểu, không chết im lặng."""
        if issubclass(kieu, KeyboardInterrupt):
            return
        nhat_ky.log().error("".join(traceback.format_exception(kieu, gia_tri, tb)))
        try:
            QtWidgets.QMessageBox.critical(
                None, "Lỗi giao diện",
                f"{nhat_ky.giai_thich(gia_tri)}\n\nChi tiết đã ghi vào:\n{log_file}")
        except Exception:
            pass
    sys.excepthook = _loi_chua_bat
    win = MainWindow()
    win.log_write(f"[log] {log_file}\n")
    win.show()
    # Mở kèm file dự án: `tachrang duong\den\ca.tachrang` (hoặc double-click nếu đã gán đuôi)
    for arg in sys.argv[1:]:
        if arg.lower().endswith(".tachrang") and Path(arg).is_file():
            QtCore.QTimer.singleShot(0, lambda a=arg: win.mo_du_an(a))
            break
    sys.exit(app.exec())


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--preview":
        show_preview(Path(sys.argv[2]))
    else:
        run_gui()
