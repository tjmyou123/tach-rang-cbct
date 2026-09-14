#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
xem_sua.py — Cửa sổ "Xem & Sửa" kiểu 3D Slicer thu nhỏ.

Hiển thị 3 mặt cắt CBCT (ngang/đứng dọc/đứng ngang) chồng màu các vùng AI đã
tách + khung 3D. Cho phép:
  - Tích chọn vùng nào hiển thị / vùng nào sẽ xuất STL
  - Đổi tên vùng (nháy đúp vào tên)
  - Tô thêm / xóa bớt trực tiếp trên lát cắt bằng bút vẽ (có Hoàn tác)
  - Thêm vùng mới hoàn toàn để tự tô
  - Hiện CBCT mờ trong khung 3D
  - Xuất lại STL cho các vùng đã tích chọn

Dữ liệu vào: ảnh CBCT đã chuẩn hóa (staged_inputs/<ca>.nii.gz) và bản đồ
nhãn gộp (labelmaps/<ca>.nii.gz + .json) do chế độ KẾT HỢP tạo ra.
"""

import json
import re
from pathlib import Path

import numpy as np
import SimpleITK as sitk
import vtk
from PySide6 import QtCore, QtGui, QtWidgets
import vtkmodules.qt
vtkmodules.qt.PyQtImpl = "PySide6"
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor

import tachrang.core.pipeline as pl
from tachrang.ui.khung_xem import KhungLat, cua_so_u8, tao_volume_ct

# Bảng màu răng (0-255) — 40 màu chọn để phân biệt rõ bằng mắt trên nền phim xám
PALETTE = [
    (230, 25, 75),  (60, 180, 75),   (255, 225, 25), (0, 130, 200),
    (245, 130, 48), (145, 30, 180),  (70, 240, 240), (240, 50, 230),
    (210, 245, 60), (250, 190, 212), (0, 128, 128),  (220, 190, 255),
    (170, 110, 40), (255, 250, 200), (128, 0, 0),    (170, 255, 195),
    (128, 128, 0),  (255, 215, 180), (65, 90, 255),  (255, 105, 97),
    (100, 220, 60), (255, 160, 0),   (90, 60, 220),  (0, 200, 160),
    (230, 90, 140), (140, 200, 255), (200, 160, 90), (160, 60, 100),
    (60, 140, 60),  (255, 130, 210), (150, 230, 200), (180, 90, 40),
    (110, 110, 255), (220, 220, 90), (40, 180, 220), (200, 60, 60),
    (120, 180, 30), (250, 140, 120), (130, 80, 160), (90, 160, 120),
]


def mau_cho_nhan(lab_id: int, name: str):
    """Màu hiển thị cho 1 nhãn: xương xám, ống TK cam, xoang xanh; răng có số
    FDI được gán MÀU CỐ ĐỊNH theo số răng (11-48 → ô 0-31), răng chưa rõ
    số dùng màu rải đều phần còn lại — các răng cạnh nhau luôn khác màu rõ."""
    n = name.lower()
    if "sinus" in n or "xoang" in n:
        return (80, 155, 255)
    if "pulp" in n or "-tuy" in n:
        return (255, 40, 40)
    if "canal" in n:
        return (255, 140, 0)
    # Xương: hàm dưới xám đá hơi lạnh, hàm trên/sọ be cát ấm -> phân biệt ngay
    if "mandible" in n or "ham-duoi" in n or "jawbone" in n:
        return (176, 188, 200)
    if "maxilla" in n or "skull" in n or "ham-tren" in n:
        return (232, 212, 172)
    m = re.search(r"fdi[ _-]?(\d\d)", n)
    if m:
        fdi = int(m.group(1))
        q, r = fdi // 10, fdi % 10
        if 1 <= q <= 4 and 1 <= r <= 8:
            return PALETTE[(q - 1) * 8 + (r - 1)]
    return PALETTE[(lab_id * 17 + 5) % len(PALETTE)]


def la_xuong(name: str) -> bool:
    n = name.lower()
    if "sinus" in n:
        return False
    return any(k in n for k in ("mandible", "maxilla", "skull", "jawbone"))


TEN_TRUC = {0: "Cắt NGANG (axial)", 1: "Đứng NGANG (coronal)", 2: "Đứng DỌC (sagittal)"}


class CuaSoXemSua(QtWidgets.QMainWindow):
    """Cửa sổ Xem & Sửa cho 1 ca."""

    def __init__(self, ct_path: Path, lm_path: Path, json_path: Path,
                 stl_dir: Path, case: str, parent=None):
        super().__init__(parent)
        self.case = case
        self.stl_dir = Path(stl_dir)
        self.lm_path = Path(lm_path)
        self.json_path = Path(json_path)
        self.setWindowTitle(f"Xem & Sửa — {case}")
        self.resize(1500, 900)

        # ── dữ liệu ──
        self.ct_img = sitk.ReadImage(str(ct_path))
        self.ct_u8 = cua_so_u8(sitk.GetArrayFromImage(self.ct_img))
        self.lm_img = sitk.ReadImage(str(lm_path))
        self.lab = sitk.GetArrayFromImage(self.lm_img).astype(np.int16)
        self.shape = (self.lab.shape[0], self.lab.shape[1], self.lab.shape[2])  # (z,y,x)
        self.sp = self.ct_img.GetSpacing()  # (sx, sy, sz)
        self.matrix = pl.physical_matrix(self.ct_img)

        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
        self.names = {int(k): v for k, v in data.get("labels", {}).items()}
        for v in np.unique(self.lab):
            if v > 0 and int(v) not in self.names:
                self.names[int(v)] = f"label-{int(v)}"
        self._lam_lut()

        self.undo_stack = []            # [(axis, k, bản sao lát)]
        self.epoch = 0                  # tăng mỗi lần nhãn đổi → khung lát vẽ lại
        self._dirty_3d = True
        self._actors = {}

        # ═══ trái: danh sách vùng + công cụ ═══
        left = QtWidgets.QWidget(); left.setMaximumWidth(360)
        lv = QtWidgets.QVBoxLayout(left)
        lv.addWidget(QtWidgets.QLabel("Các vùng đã tách (tích = hiển thị & xuất,\nnháy đúp = đổi tên):"))
        self.list = QtWidgets.QListWidget()
        self.list.itemChanged.connect(self._doi_item)
        self.list.currentItemChanged.connect(lambda *_: self._ve_lai_2d())
        lv.addWidget(self.list, stretch=1)

        row = QtWidgets.QHBoxLayout()
        self.btn_all = QtWidgets.QPushButton("Chọn hết")
        self.btn_none = QtWidgets.QPushButton("Bỏ hết")
        self.btn_new = QtWidgets.QPushButton("+ Vùng mới")
        row.addWidget(self.btn_all); row.addWidget(self.btn_none); row.addWidget(self.btn_new)
        lv.addLayout(row)
        self.btn_all.clicked.connect(lambda: self._tick_all(True))
        self.btn_none.clicked.connect(lambda: self._tick_all(False))
        self.btn_new.clicked.connect(self._vung_moi)

        gb = QtWidgets.QGroupBox("Bút sửa trên lát cắt")
        gl = QtWidgets.QGridLayout(gb)
        self.rb_xem = QtWidgets.QRadioButton("Chỉ xem"); self.rb_xem.setChecked(True)
        self.rb_to = QtWidgets.QRadioButton("Tô thêm")
        self.rb_xoa = QtWidgets.QRadioButton("Xóa bớt")
        gl.addWidget(self.rb_xem, 0, 0); gl.addWidget(self.rb_to, 0, 1); gl.addWidget(self.rb_xoa, 0, 2)
        gl.addWidget(QtWidgets.QLabel("Cỡ bút (mm):"), 1, 0)
        self.spin_but = QtWidgets.QDoubleSpinBox()
        self.spin_but.setRange(0.3, 15.0); self.spin_but.setValue(2.0); self.spin_but.setSingleStep(0.5)
        gl.addWidget(self.spin_but, 1, 1)
        self.btn_undo = QtWidgets.QPushButton("↶ Hoàn tác (Ctrl+Z)")
        gl.addWidget(self.btn_undo, 1, 2)
        self.btn_undo.clicked.connect(self.hoan_tac)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Z"), self, self.hoan_tac)
        lv.addWidget(gb)
        lv.addWidget(QtWidgets.QLabel("Tô/xóa tác động lên vùng đang chọn trong danh sách.\n"
                                      "Cuộn chuột trên ảnh = đổi lát cắt."))

        self.cb_ct3d = QtWidgets.QCheckBox("Hiện CBCT mờ trong khung 3D")
        self.cb_ct3d.toggled.connect(self._bat_tat_ct3d)
        lv.addWidget(self.cb_ct3d)

        self.btn_3d = QtWidgets.QPushButton("⟳ Cập nhật hình 3D")
        self.btn_3d.clicked.connect(self.cap_nhat_3d)
        lv.addWidget(self.btn_3d)
        self.btn_save = QtWidgets.QPushButton("💾 Lưu chỉnh sửa (bản đồ nhãn)")
        self.btn_save.clicked.connect(self.luu_nhan)
        lv.addWidget(self.btn_save)
        self.btn_xuat = QtWidgets.QPushButton("⬇ XUẤT STL các vùng đã tích")
        self.btn_xuat.setStyleSheet("font-weight:bold; padding:6px;")
        self.btn_xuat.clicked.connect(self.xuat_stl)
        lv.addWidget(self.btn_xuat)
        self.trang_thai = QtWidgets.QLabel("")
        self.trang_thai.setWordWrap(True)
        lv.addWidget(self.trang_thai)

        # ═══ phải: 2×2 = 3 lát cắt + 3D ═══
        grid_w = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(grid_w); grid.setSpacing(4)
        self.canvases = []
        self.sliders = []
        for i, (axis, r, c) in enumerate(((0, 0, 0), (1, 0, 1), (2, 1, 0))):
            cell = QtWidgets.QWidget()
            cl = QtWidgets.QVBoxLayout(cell); cl.setContentsMargins(0, 0, 0, 0); cl.setSpacing(2)
            cv = KhungLat(self, axis)
            sl = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
            sl.setRange(0, self.shape[axis] - 1); sl.setValue(cv.k)
            sl.valueChanged.connect(lambda v, cv=cv: cv.set_k(v))
            cl.addWidget(cv, stretch=1); cl.addWidget(sl)
            grid.addWidget(cell, r, c)
            self.canvases.append(cv); self.sliders.append(sl)

        self.vtk_widget = QVTKRenderWindowInteractor(grid_w)
        self.ren = vtk.vtkRenderer()
        self.ren.GradientBackgroundOn()
        self.ren.SetBackground(0.09, 0.11, 0.14); self.ren.SetBackground2(0.24, 0.27, 0.31)
        self.vtk_widget.GetRenderWindow().AddRenderer(self.ren)
        iren = self.vtk_widget.GetRenderWindow().GetInteractor()
        iren.SetInteractorStyle(vtk.vtkInteractorStyleTrackballCamera())
        grid.addWidget(self.vtk_widget, 1, 1)

        sp = QtWidgets.QSplitter()
        sp.addWidget(left); sp.addWidget(grid_w); sp.setSizes([340, 1140])
        self.setCentralWidget(sp)

        self._nap_danh_sach()
        self.vtk_widget.GetRenderWindow().Render()
        iren.Initialize()
        self.volume_actor = None
        QtCore.QTimer.singleShot(150, self.cap_nhat_3d)

    # ── bảng màu / hiển thị ──
    def _lam_lut(self):
        mx = max(list(self.names) + [1]) + 2
        self.color_lut = np.zeros((mx, 3), dtype=np.uint8)
        self.vis_lut = np.zeros(mx, dtype=bool)
        for i, nm in self.names.items():
            self.color_lut[i] = mau_cho_nhan(i, nm)

    def _nap_danh_sach(self):
        self.list.blockSignals(True)
        self.list.clear()
        for i in sorted(self.names):
            nm = self.names[i]
            it = QtWidgets.QListWidgetItem(nm)
            it.setData(QtCore.Qt.ItemDataRole.UserRole, i)
            it.setFlags(it.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable
                        | QtCore.Qt.ItemFlag.ItemIsEditable)
            it.setCheckState(QtCore.Qt.CheckState.Checked)
            px = QtGui.QPixmap(14, 14); px.fill(QtGui.QColor(*self.color_lut[i]))
            it.setIcon(QtGui.QIcon(px))
            self.list.addItem(it)
            self.vis_lut[i] = True
        self.list.blockSignals(False)
        if self.list.count():
            self.list.setCurrentRow(0)

    def _doi_item(self, it):
        i = it.data(QtCore.Qt.ItemDataRole.UserRole)
        self.vis_lut[i] = it.checkState() == QtCore.Qt.CheckState.Checked
        txt = it.text().strip()
        if txt and txt != self.names[i]:
            self.names[i] = txt
        if i in self._actors:
            self._actors[i].SetVisibility(bool(self.vis_lut[i]))
            self.vtk_widget.GetRenderWindow().Render()
        self._ve_lai_2d()

    def _tick_all(self, on):
        st = QtCore.Qt.CheckState.Checked if on else QtCore.Qt.CheckState.Unchecked
        for j in range(self.list.count()):
            self.list.item(j).setCheckState(st)

    def _vung_moi(self):
        i = int(max(list(self.names) + [200]) + 1)
        self.names[i] = f"Vung-moi-{i - 200}"
        self._lam_lut()
        self._nap_danh_sach()
        self.list.setCurrentRow(self.list.count() - 1)
        self.rb_to.setChecked(True)
        self.trang_thai.setText(f"Đã thêm '{self.names[i]}' — chọn nó rồi tô lên lát cắt.")

    # ── bút vẽ ──
    def che_do_ve(self):
        return self.rb_to.isChecked() or self.rb_xoa.isChecked()

    def brush_mm(self):
        return float(self.spin_but.value())

    def _nhan_dang_chon(self):
        it = self.list.currentItem()
        return None if it is None else int(it.data(QtCore.Qt.ItemDataRole.UserRole))

    def bat_dau_net_ve(self, axis, k):
        pl_ = self._lay_lat(axis, k)
        self.undo_stack.append((axis, k, pl_.copy()))
        if len(self.undo_stack) > 20:
            self.undo_stack.pop(0)

    def _lay_lat(self, axis, k):
        if axis == 0:
            return self.lab[k]
        if axis == 1:
            return self.lab[:, k, :]
        return self.lab[:, :, k]

    def to_tai(self, axis, k, r, c):
        i = self._nhan_dang_chon()
        if i is None:
            return
        plane = self._lay_lat(axis, k)
        mm = self.brush_mm()
        if axis == 0:
            rsp, csp = self.sp[1], self.sp[0]
        elif axis == 1:
            rsp, csp = self.sp[2], self.sp[0]
        else:
            rsp, csp = self.sp[2], self.sp[1]
        rr, rc = max(mm / rsp, 0.6), max(mm / csp, 0.6)
        r0, r1 = int(max(r - rr, 0)), int(min(r + rr + 1, plane.shape[0]))
        c0, c1 = int(max(c - rc, 0)), int(min(c + rc + 1, plane.shape[1]))
        if r0 >= r1 or c0 >= c1:
            return
        yy, xx = np.ogrid[r0:r1, c0:c1]
        disk = ((yy - r) / rr) ** 2 + ((xx - c) / rc) ** 2 <= 1.0
        sub = plane[r0:r1, c0:c1]
        if self.rb_to.isChecked():
            sub[disk] = np.int16(i)
        else:
            sub[disk & (sub == i)] = 0
        self._dirty_3d = True
        self._ve_lai_2d()

    def hoan_tac(self):
        if not self.undo_stack:
            return
        axis, k, cu = self.undo_stack.pop()
        self._lay_lat(axis, k)[:] = cu
        self._dirty_3d = True
        self._ve_lai_2d()
        self.trang_thai.setText("Đã hoàn tác 1 nét vẽ.")

    def dong_bo_thanh_truot(self, axis, k):
        for cv, sl in zip(self.canvases, self.sliders):
            if cv.axis == axis:
                sl.blockSignals(True); sl.setValue(k); sl.blockSignals(False)

    def _ve_lai_2d(self):
        self.epoch += 1
        for cv in self.canvases:
            cv.update()

    # ── 3D ──
    def cap_nhat_3d(self):
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        try:
            from scipy import ndimage
            for a in self._actors.values():
                self.ren.RemoveActor(a)
            self._actors = {}
            boxes = ndimage.find_objects(np.maximum(self.lab, 0))
            for i in sorted(self.names):
                if i - 1 >= len(boxes) or boxes[i - 1] is None:
                    continue
                sl = boxes[i - 1]
                pad = 6
                z0 = max(sl[0].start - pad, 0); z1 = min(sl[0].stop + pad, self.shape[0])
                y0 = max(sl[1].start - pad, 0); y1 = min(sl[1].stop + pad, self.shape[1])
                x0 = max(sl[2].start - pad, 0); x1 = min(sl[2].stop + pad, self.shape[2])
                crop = self.lab[z0:z1, y0:y1, x0:x1] == i
                if crop.sum() < 30:
                    continue
                actor = self._actor_tu_mask(crop, (float(x0), float(y0), float(z0)), i)
                self.ren.AddActor(actor)
                actor.SetVisibility(bool(self.vis_lut[i]))
                self._actors[i] = actor
            self.ren.ResetCamera()
            self.vtk_widget.GetRenderWindow().Render()
            self._dirty_3d = False
            self.trang_thai.setText(f"Hình 3D: {len(self._actors)} vùng.")
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

    def _actor_tu_mask(self, mask, offset_xyz, lab_id):
        from vtk.util.numpy_support import numpy_to_vtk
        vimg = vtk.vtkImageData()
        z, y, x = mask.shape
        vimg.SetDimensions(x, y, z)
        vimg.SetOrigin(*offset_xyz)
        vimg.GetPointData().SetScalars(
            numpy_to_vtk((mask.astype(np.uint8) * 100).ravel(), deep=True))
        vox = pl.voxel_sizes_mm(self.matrix)
        stds = [min(0.6 / max(v, 1e-6), 3.0) for v in vox]
        cast = vtk.vtkImageCast(); cast.SetInputData(vimg); cast.SetOutputScalarTypeToFloat()
        gauss = vtk.vtkImageGaussianSmooth()
        gauss.SetInputConnection(cast.GetOutputPort())
        gauss.SetStandardDeviations(*stds); gauss.SetRadiusFactors(3, 3, 3)
        con = vtk.vtkFlyingEdges3D()
        con.SetInputConnection(gauss.GetOutputPort())
        con.SetValue(0, 50.0); con.ComputeNormalsOff(); con.ComputeScalarsOff()
        tr = vtk.vtkTransform(); tr.SetMatrix(self.matrix)
        tp = vtk.vtkTransformPolyDataFilter()
        tp.SetInputConnection(con.GetOutputPort()); tp.SetTransform(tr)
        sm = vtk.vtkWindowedSincPolyDataFilter()
        sm.SetInputConnection(tp.GetOutputPort())
        sm.SetNumberOfIterations(10); sm.SetPassBand(0.01)
        sm.BoundarySmoothingOn(); sm.NonManifoldSmoothingOn(); sm.NormalizeCoordinatesOn()
        mp = vtk.vtkPolyDataMapper(); mp.SetInputConnection(sm.GetOutputPort())
        mp.ScalarVisibilityOff()
        a = vtk.vtkActor(); a.SetMapper(mp)
        col = self.color_lut[lab_id] / 255.0
        a.GetProperty().SetColor(*col)
        if la_xuong(self.names.get(lab_id, "")):
            a.GetProperty().SetOpacity(0.35)
        elif "sinus" in self.names.get(lab_id, "").lower():
            a.GetProperty().SetOpacity(0.5)
        a.GetProperty().SetSpecular(0.25); a.GetProperty().SetSpecularPower(20)
        return a

    def _bat_tat_ct3d(self, on):
        if on and self.volume_actor is None:
            self.volume_actor = tao_volume_ct(self.ct_u8, self.matrix)
            self.ren.AddVolume(self.volume_actor)
        if self.volume_actor is not None:
            self.volume_actor.SetVisibility(bool(on))
            self.vtk_widget.GetRenderWindow().Render()

    # ── lưu / xuất ──
    def luu_nhan(self):
        img = sitk.GetImageFromArray(self.lab)
        img.CopyInformation(self.lm_img)
        sitk.WriteImage(img, str(self.lm_path), useCompression=True)
        with open(self.json_path, "w", encoding="utf-8") as f:
            json.dump({"case": self.case,
                       "labels": {str(k): v for k, v in sorted(self.names.items())}},
                      f, ensure_ascii=False, indent=1)
        self.trang_thai.setText("Đã lưu bản đồ nhãn + tên vùng.")

    def xuat_stl(self):
        ids = [self.list.item(j).data(QtCore.Qt.ItemDataRole.UserRole)
               for j in range(self.list.count())
               if self.list.item(j).checkState() == QtCore.Qt.CheckState.Checked]
        if not ids:
            QtWidgets.QMessageBox.information(self, "Chưa chọn vùng",
                                              "Hãy tích chọn ít nhất 1 vùng để xuất.")
            return
        self.luu_nhan()
        self.stl_dir.mkdir(parents=True, exist_ok=True)
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        ok = 0
        try:
            for n, i in enumerate(ids, 1):
                nm = pl.sanitize(self.names[i])
                self.trang_thai.setText(f"Đang xuất {n}/{len(ids)}: {nm} ...")
                QtWidgets.QApplication.processEvents()
                res = pl.export_labeled_mask(self.lab == i, self.matrix,
                                             self.stl_dir / f"{self.case}_{nm}.stl",
                                             30, 15, 0.01, 0.0)
                if res is not None:
                    ok += 1
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        self.trang_thai.setText(f"Đã xuất {ok}/{len(ids)} file STL vào {self.stl_dir}")
        QtWidgets.QMessageBox.information(
            self, "Xuất xong",
            f"Đã xuất {ok} file STL vào:\n{self.stl_dir}\n\n"
            "Các vùng không tích không bị xóa file cũ — tự xóa tay nếu không cần.")


def mo_xem_sua(out_dir: Path, case: str, parent=None):
    """Mở cửa sổ Xem & Sửa cho 1 ca trong thư mục kết quả. Trả về cửa sổ (hoặc None)."""
    out_dir = Path(out_dir)
    ct = out_dir / "staged_inputs" / f"{case}.nii.gz"
    lm = out_dir / "labelmaps" / f"{case}.nii.gz"
    js = out_dir / "labelmaps" / f"{case}.json"
    if not ct.is_file():
        QtWidgets.QMessageBox.warning(parent, "Thiếu ảnh CBCT",
                                      f"Không thấy {ct}.\nHãy chạy tách răng cho ca này trước.")
        return None
    if not (lm.is_file() and js.is_file()):
        QtWidgets.QMessageBox.warning(
            parent, "Chưa có bản đồ nhãn",
            "Ca này chưa có bản đồ nhãn để chỉnh sửa.\n"
            "Hãy chạy lại bằng chế độ KẾT HỢP (bản mới) — pipeline sẽ tạo "
            "labelmaps/<ca>.nii.gz tự động.")
        return None
    w = CuaSoXemSua(ct, lm, js, out_dir / "stl" / case, case, parent)
    w.show()
    return w
