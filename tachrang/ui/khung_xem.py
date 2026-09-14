#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
khung_xem.py — Khung xem lát cắt CBCT dùng chung cho giao diện chính và Xem & Sửa.

KhungLat: 1 mặt cắt (axial/coronal/sagittal) vẽ CT + màu nhãn (nếu có).
  - Lăn chuột            : đổi lát cắt
  - Ctrl + lăn chuột     : phóng to / thu nhỏ quanh con trỏ
  - Alt + lăn chuột      : XOAY lát cắt (nghiêng mặt phẳng cắt, ±45°)
  - Kéo chuột phải/giữa  : di chuyển ảnh (khi đã phóng to)
  - Nháy đúp             : trở về vừa khung + hết xoay
  - Chuột trái           : tô / xóa (chỉ khi nguồn dữ liệu bật chế độ vẽ,
                           tạm khóa khi đang xoay lát)
  - ĐO: nguồn trả che_do_do() = "kc" (2 điểm -> mm) hoặc "goc" (3 điểm, đỉnh ở giữa
    -> độ); các số đo lưu trong nguon.do_dac (theo lát) và vẽ lại khi quay về lát đó

Ảnh lát đã pha màu được cache lại nên cuộn/di chuột mượt, không phải tính
lại mỗi lần vẽ — đây là nguyên nhân giật/lỗi hiển thị trước kia.
"""

from pathlib import Path

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

TEN_TRUC = {0: "Cắt NGANG (axial)", 1: "Đứng NGANG (coronal)", 2: "Đứng DỌC (sagittal)"}
MAU_TRUC = {0: (235, 100, 90), 1: (90, 200, 130), 2: (245, 205, 80)}  # màu đường kẻ lát
MAU_DO = {"kc": (80, 230, 255), "goc": (255, 120, 255)}
IMG_EXTS = (".nii.gz", ".nii", ".nrrd", ".nhdr", ".gipl.gz", ".gipl", ".mha", ".mhd")


def cat_mesh_lat(V: np.ndarray, axis: int, k: int) -> np.ndarray:
    """Giao tuyến của một mesh với mặt phẳng lát.

    V    : (N, 3, 3) tọa độ 3 đỉnh mỗi tam giác theo chỉ số voxel (z, y, x), tâm voxel = số nguyên
    axis : 0 axial / 1 coronal / 2 sagittal, k: chỉ số lát
    Trả về (M, 2, 2) các đoạn thẳng [(r, c), (r, c)] liên tục trên lát (tâm voxel = chỉ số + 0.5,
    cùng quy ước với công cụ đo). Thuần numpy, ~10-30 ms cho 1 triệu tam giác.
    """
    if V is None or len(V) == 0:
        return np.zeros((0, 2, 2), np.float32)
    d = V[:, :, axis] - np.float32(k)
    d = np.where(d == 0, np.float32(1e-6), d)      # đỉnh nằm đúng mặt phẳng: coi như lệch nhỏ
    cross = (d.min(1) < 0) & (d.max(1) > 0)
    if not cross.any():
        return np.zeros((0, 2, 2), np.float32)
    v = V[cross]
    dd = d[cross]
    pts, masks = [], []
    for i, j in ((0, 1), (1, 2), (2, 0)):
        m = (dd[:, i] * dd[:, j]) < 0
        t = dd[:, i] / (dd[:, i] - dd[:, j])
        pts.append(v[:, i, :] + t[:, None] * (v[:, j, :] - v[:, i, :]))
        masks.append(m)
    P = np.stack(pts, 1)                       # (M, 3 cạnh, 3 tọa độ)
    Mk = np.stack(masks, 1)                    # (M, 3) — đúng 2 cạnh True mỗi tam giác
    order = np.argsort(~Mk, axis=1, kind="stable")[:, :2]
    seg = np.take_along_axis(P, order[:, :, None], axis=1)   # (M, 2, 3) zyx
    ax_r, ax_c = {0: (1, 2), 1: (0, 2), 2: (0, 1)}[axis]
    out = np.stack([seg[:, :, ax_r], seg[:, :, ax_c]], -1) + 0.5
    return out.astype(np.float32)


def mesh_sang_chi_so_voxel(polydata, matrix) -> np.ndarray:
    """vtkPolyData (tọa độ vật lý LPS) + ma trận index→LPS của ảnh -> V (N,3,3) theo (z,y,x) voxel."""
    import vtk
    from vtk.util.numpy_support import vtk_to_numpy
    tri = vtk.vtkTriangleFilter()
    tri.SetInputData(polydata)
    tri.Update()
    pd = tri.GetOutput()
    if pd.GetNumberOfPoints() == 0 or pd.GetNumberOfPolys() == 0:
        return np.zeros((0, 3, 3), np.float32)
    pts = vtk_to_numpy(pd.GetPoints().GetData()).astype(np.float64)
    cells = vtk_to_numpy(pd.GetPolys().GetData()).reshape(-1, 4)[:, 1:]
    M = np.array([[matrix.GetElement(i, j) for j in range(4)] for i in range(4)], float)
    Mi = np.linalg.inv(M)
    idx = pts @ Mi[:3, :3].T + Mi[:3, 3]            # (i=x, j=y, k=z) chỉ số voxel
    zyx = idx[:, ::-1].astype(np.float32)
    return zyx[cells]                               # (N, 3, 3)


def gia_tri_do(pts, kieu, rsp, csp):
    """Giá trị số đo từ các điểm (r, c) liên tục trên lát: (số, chuỗi hiển thị).
    kc  : khoảng cách 2 điểm (mm)
    goc : góc tại điểm giữa giữa 2 đoạn (độ)"""
    if kieu == "kc" and len(pts) >= 2:
        (r1, c1), (r2, c2) = pts[0], pts[1]
        d = float(np.hypot((r2 - r1) * rsp, (c2 - c1) * csp))
        return d, f"{d:.1f} mm"
    if kieu == "goc" and len(pts) >= 3:
        (r1, c1), (r0, c0), (r2, c2) = pts[0], pts[1], pts[2]
        v1 = np.array([(r1 - r0) * rsp, (c1 - c0) * csp])
        v2 = np.array([(r2 - r0) * rsp, (c2 - c0) * csp])
        n1, n2 = np.linalg.norm(v1), np.linalg.norm(v2)
        if n1 < 1e-9 or n2 < 1e-9:
            return 0.0, "0.0°"
        g = float(np.degrees(np.arccos(np.clip(v1 @ v2 / (n1 * n2), -1.0, 1.0))))
        return g, f"{g:.1f}°"
    return None, ""


def cua_so_u8(ct: np.ndarray) -> np.ndarray:
    """Đưa ảnh CT về thang xám 0-255 (cửa sổ 1%..99.5%)."""
    ct = ct.astype(np.float32)
    lo, hi = np.percentile(ct, (1.0, 99.5))
    return np.clip((ct - lo) * (255.0 / max(hi - lo, 1e-6)), 0, 255).astype(np.uint8)


def quet_va_doc_dicom(root: Path):
    """Quét 1 thư mục (kể cả lồng sâu) tìm ảnh CBCT của MỘT ca.

    Trả về (img, so_ca, so_lat):
      - nhiều bệnh nhân/ca khác nhau -> (None, so_ca, 0)
      - không tìm thấy gì            -> (None, 0, 0)
      - đúng 1 ca                    -> (ảnh SimpleITK, 1, số lát)
    """
    import SimpleITK as sitk

    root = Path(root)
    # Trường hợp thư mục chứa sẵn file ảnh 3D (nii/nrrd...)
    imgs = sorted(p for p in root.iterdir()
                  if p.is_file() and p.name.lower().endswith(IMG_EXTS))
    if imgs:
        if len(imgs) > 1:
            return None, len(imgs), 0
        img = sitk.ReadImage(str(imgs[0]))
        return img, 1, int(img.GetSize()[2])

    reader = sitk.ImageSeriesReader()
    dirs = [root]
    for p in root.rglob("*"):
        if p.is_dir():
            dirs.append(p)
            if len(dirs) > 300:      # tránh quét nhầm cả ổ đĩa
                break
    series = []
    for d in dirs:
        try:
            sids = reader.GetGDCMSeriesIDs(str(d))
        except Exception:
            continue
        for sid in sids:
            try:
                files = reader.GetGDCMSeriesFileNames(str(d), sid)
            except Exception:
                continue
            if len(files) >= 10:
                series.append(list(files))
    if not series:
        return None, 0, 0

    # Mỗi chuỗi ảnh thuộc bệnh nhân nào? (tag 0010|0020 = mã BN, 0010|0010 = tên)
    benh_nhan = set()
    for files in series:
        fr = sitk.ImageFileReader()
        fr.SetFileName(files[0])
        try:
            fr.ReadImageInformation()
            pid = fr.GetMetaData("0010|0020") if fr.HasMetaDataKey("0010|0020") else ""
            ten = fr.GetMetaData("0010|0010") if fr.HasMetaDataKey("0010|0010") else ""
            benh_nhan.add((pid.strip(), ten.strip()))
        except Exception:
            pass
    if len(benh_nhan) > 1:
        return None, len(benh_nhan), 0

    best = max(series, key=len)
    reader.SetFileNames(best)
    return reader.Execute(), 1, len(best)


def tao_volume_ct(ct_u8: np.ndarray, matrix, step: int = 2,
                  nguong: float = 120.0, do_dam: float = 0.28):
    """Tạo vtkVolume hiển thị CBCT mờ kiểu xương (giảm mẫu cho nhẹ máy)."""
    import vtk
    from vtk.util.numpy_support import numpy_to_vtk

    v = np.ascontiguousarray(ct_u8[::step, ::step, ::step])
    vimg = vtk.vtkImageData()
    vimg.SetDimensions(v.shape[2], v.shape[1], v.shape[0])
    vimg.SetSpacing(float(step), float(step), float(step))
    vimg.GetPointData().SetScalars(numpy_to_vtk(v.ravel(), deep=True))
    mapper = vtk.vtkSmartVolumeMapper()
    mapper.SetInputData(vimg)
    prop = vtk.vtkVolumeProperty()
    prop.SetColor(vtk.vtkColorTransferFunction())
    prop.SetScalarOpacity(vtk.vtkPiecewiseFunction())
    prop.ShadeOn()
    prop.SetInterpolationTypeToLinear()
    vol = vtk.vtkVolume()
    vol.SetMapper(mapper)
    vol.SetProperty(prop)
    if matrix is not None:
        vol.SetUserMatrix(matrix)
    dat_kieu_volume(vol, nguong, do_dam)
    return vol


def dat_kieu_volume(vol, nguong: float, do_dam: float):
    """Đổi kiểu hiển thị khối CBCT đang có (không cần tạo lại).

    nguong : mức xám (0-255) bắt đầu hiện — kéo THẤP thấy cả da/mô mềm,
             kéo CAO chỉ còn răng/xương đặc.
    do_dam : độ đậm tối đa (0-1) — cao = khối đặc rõ, thấp = mờ như sương.
    Gọi xong nhớ Render() lại cửa sổ 3D.
    """
    n = float(min(max(nguong, 1.0), 250.0))
    d = float(min(max(do_dam, 0.01), 1.0))
    prop = vol.GetProperty()
    ctf = prop.GetRGBTransferFunction()
    ctf.RemoveAllPoints()
    ctf.AddRGBPoint(0, 0, 0, 0)
    ctf.AddRGBPoint(n, 0.45, 0.40, 0.35)
    ctf.AddRGBPoint(min(n + 60.0, 254.0), 0.78, 0.74, 0.68)
    ctf.AddRGBPoint(255, 1.0, 0.98, 0.92)
    otf = prop.GetScalarOpacity()
    otf.RemoveAllPoints()
    otf.AddPoint(0, 0.0)
    otf.AddPoint(n, 0.0)
    otf.AddPoint(min(n + 50.0, 254.0), 0.21 * d)
    otf.AddPoint(255, d)


class NguonXem:
    """Nguồn dữ liệu CHỈ XEM cho KhungLat (dùng ở giao diện chính)."""

    def __init__(self):
        self.ct_u8 = None
        self.lab = None
        self.vis_lut = None
        self.color_lut = None
        self.sp = (1.0, 1.0, 1.0)
        self.shape = (1, 1, 1)
        self.epoch = 0
        self.khi_doi_lat = None      # callback (axis, k) để đồng bộ thanh trượt
        # Cửa sổ hiển thị lát cắt (trên thang 0-255 của ct_u8): mức giữa + độ rộng
        self.cua_so = (128.0, 256.0)
        self.lut_xam = None          # None = giữ nguyên
        self.khi_doi_cua_so = None   # callback (level, window) khi kéo chuởt phải
        # Scan hàm vẽ viền trên lát: [{"V": (N,3,3) zyx, "mau": (r,g,b), "hien": bool}]
        self.scans = []
        self.scan_epoch = 0          # tăng khi danh sách/hiển thị scan đổi -> xóa cache
        self._scan_cache = {}

    def dat_cua_so(self, level: float, window: float):
        """Đổi sáng/tương phản lát cắt (không đụng dữ liệu gốc) — như W/L của CT."""
        level = float(min(max(level, -50.0), 305.0))
        window = float(min(max(window, 8.0), 600.0))
        self.cua_so = (level, window)
        if abs(level - 128.0) < 0.5 and abs(window - 256.0) < 0.5:
            self.lut_xam = None
            return
        i = np.arange(256, dtype=np.float32)
        lo = level - window / 2.0
        self.lut_xam = np.clip((i - lo) * (255.0 / window), 0, 255).astype(np.uint8)

    def che_do_ve(self):
        return False

    def che_do_do(self):
        """"kc" / "goc" khi đang đo, None khi không."""
        return None

    def dong_bo_thanh_truot(self, axis, k):
        if self.khi_doi_lat:
            self.khi_doi_lat(axis, k)


class KhungLat(QtWidgets.QWidget):
    """Khung vẽ 1 mặt cắt CBCT + màu nhãn, có phóng to / di ảnh / tô vẽ."""

    def __init__(self, nguon, axis):
        super().__init__()
        self.nguon = nguon
        self.axis = axis
        if not hasattr(nguon, "goc"):
            nguon.goc = [0.0, 0.0, 0.0]   # độ xoay quanh trục z / y / x (độ)
        self.k = max(int(nguon.shape[axis]) // 2, 0)
        self.zoom = 1.0
        self.pan = QtCore.QPointF(0.0, 0.0)
        self.setMinimumSize(200, 170)
        self.setMouseTracking(True)
        self._mouse = None
        self._painting = False
        self._nav = False
        self._pan_last = None
        self._wl_last = None
        self._cache_key = None
        self._cache_qimg = None

    # ── dữ liệu ──────────────────────────────────────────────────────────
    def dat_lai(self):
        """Gọi khi nguồn có dữ liệu mới: về lát giữa, hết phóng to/xoay."""
        self.k = max(int(self.nguon.shape[self.axis]) // 2, 0)
        self.zoom = 1.0
        self.pan = QtCore.QPointF(0.0, 0.0)
        self.nguon.goc[:] = [0.0, 0.0, 0.0]
        self._cache_key = None
        self.update()

    def _hinh_dang(self):
        """(số hàng, số cột, mm/hàng, mm/cột, lật) của lát — không đụng dữ liệu."""
        n = self.nguon
        if self.axis == 0:
            return n.shape[1], n.shape[2], n.sp[1], n.sp[0], False
        if self.axis == 1:
            return n.shape[0], n.shape[2], n.sp[2], n.sp[0], True
        return n.shape[0], n.shape[1], n.sp[2], n.sp[1], True

    def _dang_xoay(self):
        return max(abs(g) for g in self.nguon.goc) >= 0.01

    def _R(self):
        """Ma trận xoay gộp (tác động lên vectơ mm theo thứ tự z,y,x)."""
        gz, gy, gx = (np.deg2rad(g) for g in self.nguon.goc)
        cz, sz_ = np.cos(gz), np.sin(gz)
        cy, sy_ = np.cos(gy), np.sin(gy)
        cx, sx_ = np.cos(gx), np.sin(gx)
        Rz = np.array([[1, 0, 0], [0, cz, -sz_], [0, sz_, cz]])
        Ry = np.array([[cy, 0, sy_], [0, 1, 0], [-sy_, 0, cy]])
        Rx = np.array([[cx, -sx_, 0], [sx_, cx, 0], [0, 0, 1]])
        return Rz @ Ry @ Rx

    def _lat_xoay(self, k, rows, cols):
        """Cắt lát XIÊN qua khối ảnh theo góc xoay hiện tại (quanh tâm khối)."""
        from scipy import ndimage

        n = self.nguon
        spz = np.array([n.sp[2], n.sp[1], n.sp[0]], dtype=np.float64)  # mm (z,y,x)
        C = (np.array(n.shape, dtype=np.float64) - 1.0) / 2.0 * spz
        R = self._R()
        if self.axis == 0:
            p0 = np.array([k, 0, 0]); er = np.array([0, 1, 0]); ec = np.array([0, 0, 1])
        elif self.axis == 1:
            p0 = np.array([0, k, 0]); er = np.array([1, 0, 0]); ec = np.array([0, 0, 1])
        else:
            p0 = np.array([0, 0, k]); er = np.array([1, 0, 0]); ec = np.array([0, 1, 0])
        base = R @ (p0 * spz - C) + C
        vr = R @ (er * spz)
        vc = R @ (ec * spz)
        ii = np.arange(rows, dtype=np.float32).reshape(rows, 1)
        jj = np.arange(cols, dtype=np.float32).reshape(1, cols)
        q = np.empty((3, rows, cols), dtype=np.float32)
        for a in range(3):
            q[a] = (base[a] + vr[a] * ii + vc[a] * jj) / spz[a]
        g = ndimage.map_coordinates(n.ct_u8, q, order=1, cval=0)
        l = None
        if n.lab is not None:
            l = ndimage.map_coordinates(n.lab, q, order=0, cval=0)
        return g, l

    def _slices(self):
        n = self.nguon
        k = int(np.clip(self.k, 0, n.shape[self.axis] - 1))
        rows, cols, rsp, csp, flip = self._hinh_dang()
        if self._dang_xoay():
            g, l = self._lat_xoay(k, rows, cols)
            return g, l, rsp, csp, flip
        if self.axis == 0:      # axial: hàng=y, cột=x
            g = n.ct_u8[k]
            l = None if n.lab is None else n.lab[k]
        elif self.axis == 1:    # coronal: hàng=z, cột=x
            g = n.ct_u8[:, k, :]
            l = None if n.lab is None else n.lab[:, k, :]
        else:                   # sagittal: hàng=z, cột=y
            g = n.ct_u8[:, :, k]
            l = None if n.lab is None else n.lab[:, :, k]
        return g, l, rsp, csp, flip

    def _anh_lat(self):
        """QImage của lát hiện tại (cache theo lát + phiên bản nhãn + góc xoay)."""
        key = (self.k, getattr(self.nguon, "epoch", 0), tuple(self.nguon.goc),
               getattr(self.nguon, "cua_so", None))
        if key == self._cache_key and self._cache_qimg is not None:
            return self._cache_qimg
        g, l, rsp, csp, flip = self._slices()
        if flip:
            g = g[::-1]
            l = None if l is None else l[::-1]
        lut_xam = getattr(self.nguon, "lut_xam", None)
        if lut_xam is not None:
            g = lut_xam[np.asarray(g, dtype=np.uint8)]
        rgb = np.repeat(g[:, :, None], 3, axis=2).astype(np.uint8)
        if l is not None and self.nguon.vis_lut is not None:
            vis = self.nguon.vis_lut
            lut = self.nguon.color_lut
            li = np.clip(l, 0, len(vis) - 1)
            m = (l > 0) & vis[li]
            if m.any():
                rgb[m] = (rgb[m] * 0.45 + lut[li[m]] * 0.55).astype(np.uint8)
        rgb = np.ascontiguousarray(rgb)
        h, w = rgb.shape[:2]
        qimg = QtGui.QImage(rgb.data, w, h, w * 3,
                            QtGui.QImage.Format.Format_RGB888).copy()
        self._cache_key = key
        self._cache_qimg = qimg
        return qimg

    def _khung_anh(self):
        """(QRectF nơi vẽ ảnh, số hàng, số cột) theo mm + zoom/pan hiện tại."""
        rows, cols, rsp, csp, _ = self._hinh_dang()
        W, H = max(self.width(), 1), max(self.height(), 1)
        w_mm, h_mm = max(cols * csp, 1e-6), max(rows * rsp, 1e-6)
        s = min(W / w_mm, H / h_mm) * 0.98 * self.zoom
        w, h = w_mm * s, h_mm * s
        cx = W / 2.0 + self.pan.x()
        cy = H / 2.0 + self.pan.y()
        return QtCore.QRectF(cx - w / 2.0, cy - h / 2.0, w, h), rows, cols

    # ── vẽ ───────────────────────────────────────────────────────────────
    def paintEvent(self, ev):
        p = QtGui.QPainter(self)
        p.fillRect(self.rect(), QtGui.QColor(12, 14, 17))
        n = self.nguon
        if n.ct_u8 is None:
            p.setPen(QtGui.QColor(140, 148, 155))
            p.drawText(self.rect(), QtCore.Qt.AlignmentFlag.AlignCenter,
                       "Chưa nạp CBCT — hãy chọn thư mục DICOM")
            p.end()
            return
        rect, rows, cols = self._khung_anh()
        p.drawImage(rect, self._anh_lat())
        self._ve_duong_lat(p, rect, rows, cols)
        p.setPen(QtGui.QColor(*MAU_TRUC[self.axis]))
        y_text = 16
        p.drawText(8, y_text, f"{TEN_TRUC[self.axis]}  —  lát {self.k + 1}/{n.shape[self.axis]}")
        p.setPen(QtGui.QColor(210, 210, 210))
        if self.zoom > 1.001:
            y_text += 16
            p.drawText(8, y_text, f"phóng to ×{self.zoom:.1f} — nháy đúp để về vừa khung")
        if self._dang_xoay():
            y_text += 16
            goc = self.nguon.goc[self.axis]
            p.setPen(QtGui.QColor(255, 210, 120))
            p.drawText(8, y_text, f"xoay {goc:+.0f}° (Alt+lăn chuột) — nháy đúp: hết xoay")
            if n.che_do_ve():
                y_text += 16
                p.drawText(8, y_text, "tô vẽ tạm khóa khi đang xoay lát")
            p.setPen(QtGui.QColor(210, 210, 210))
        if self._mouse is not None and n.che_do_ve() and not self._dang_xoay():
            _, _, rsp, csp, _ = self._hinh_dang()
            mm = self.nguon.brush_mm()
            rr = mm / csp * (rect.width() / cols)
            p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 0), 1))
            p.drawEllipse(self._mouse, rr, rr)
        if not self._dang_xoay():
            self._ve_scan(p, rect, rows, cols)
            self._ve_so_do(p, rect, rows, cols)
        p.end()

    # ── viền scan hàm trên lát ──
    def _ve_scan(self, p, rect, rows, cols):
        n = self.nguon
        scans = getattr(n, "scans", None) or []
        if not scans:
            return
        _, _, _, _, flip = self._hinh_dang()
        cache = getattr(n, "_scan_cache", None)
        if cache is None:
            cache = n._scan_cache = {}
        ep = getattr(n, "scan_epoch", 0)
        sx, sy = rect.width() / cols, rect.height() / rows
        for i, sc in enumerate(scans):
            if not sc.get("hien", True):
                continue
            key = (i, self.axis, self.k, ep)
            seg = cache.get(key)
            if seg is None:
                seg = cat_mesh_lat(sc["V"], self.axis, self.k)
                if len(cache) > 600:
                    cache.clear()
                cache[key] = seg
            if len(seg) == 0:
                continue
            r = seg[:, :, 0]
            if flip:
                r = rows - r
            xs = rect.x() + seg[:, :, 1] * sx
            ys = rect.y() + r * sy
            pen = QtGui.QPen(QtGui.QColor(*sc.get("mau", (89, 217, 242))), 1.6)
            pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            lines = [QtCore.QLineF(float(xs[j, 0]), float(ys[j, 0]),
                                   float(xs[j, 1]), float(ys[j, 1]))
                     for j in range(len(seg))]
            p.drawLines(lines)

    # ── đo khoảng cách / góc ──
    def _che_do_do(self):
        f = getattr(self.nguon, "che_do_do", None)
        return f() if f is not None else None

    def _diem_man(self, r, c, rect, rows, cols, flip):
        """(r, c) liên tục trên lát -> điểm trên màn hình."""
        rr = (rows - r) if flip else r
        return QtCore.QPointF(rect.x() + c / cols * rect.width(),
                              rect.y() + rr / rows * rect.height())

    def _to_voxel_f(self, pos):
        """Vị trí chuột -> (r, c) LIÊN TỤC (tâm voxel = chỉ số + 0.5) để đo chính xác."""
        rect, rows, cols = self._khung_anh()
        if rect.width() <= 0 or rect.height() <= 0:
            return None
        fx = (pos.x() - rect.x()) / rect.width() * cols
        fy = (pos.y() - rect.y()) / rect.height() * rows
        if not (0 <= fx < cols and 0 <= fy < rows):
            return None
        flip = self._hinh_dang()[4]
        r = (rows - fy) if flip else fy
        return float(r), float(fx)

    def _them_diem_do(self, pos):
        n = self.nguon
        kieu = self._che_do_do()
        v = self._to_voxel_f(pos)
        if kieu is None or v is None:
            return
        if not hasattr(n, "do_dac") or n.do_dac is None:
            n.do_dac = []
        ds = n.do_dac
        cur = None
        if ds and ds[-1].get("dang_ve") and ds[-1]["axis"] == self.axis \
                and ds[-1]["k"] == self.k and ds[-1]["kieu"] == kieu:
            cur = ds[-1]
        if cur is None:
            # bỏ số đo đang vẽ dở ở lát/khung khác
            n.do_dac = [d for d in ds if not d.get("dang_ve")]
            cur = {"axis": self.axis, "k": self.k, "kieu": kieu, "pts": [],
                   "dang_ve": True, "gia_tri": None, "chu": ""}
            n.do_dac.append(cur)
        cur["pts"].append(v)
        can = 2 if kieu == "kc" else 3
        if len(cur["pts"]) >= can:
            _, _, rsp, csp, _ = self._hinh_dang()
            cur["dang_ve"] = False
            cur["gia_tri"], cur["chu"] = gia_tri_do(cur["pts"], kieu, rsp, csp)
            xong = getattr(n, "khi_do_xong", None)
            if xong is not None:
                xong(cur)
        self.update()

    def _ve_so_do(self, p, rect, rows, cols):
        ds = getattr(self.nguon, "do_dac", None) or []
        _, _, rsp, csp, flip = self._hinh_dang()
        font = p.font()
        font.setBold(True)
        p.setFont(font)
        for d in ds:
            if d["axis"] != self.axis or d["k"] != self.k:
                continue
            mau = QtGui.QColor(*MAU_DO.get(d["kieu"], (255, 255, 255)))
            pts = [self._diem_man(r, c, rect, rows, cols, flip) for r, c in d["pts"]]
            if d.get("dang_ve") and self._mouse is not None and pts:
                pts_ve = pts + [self._mouse]
                pen = QtGui.QPen(mau, 1, QtCore.Qt.PenStyle.DashLine)
            else:
                pts_ve = pts
                pen = QtGui.QPen(mau, 2)
            p.setPen(pen)
            for a, b in zip(pts_ve[:-1], pts_ve[1:]):
                p.drawLine(a, b)
            p.setPen(QtGui.QPen(mau, 2))
            p.setBrush(QtGui.QBrush(mau))
            for q in pts:
                p.drawEllipse(q, 3.0, 3.0)
            p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            # chữ: giá trị đã xong, hoặc giá trị tạm theo con trỏ
            chu = d.get("chu", "")
            if d.get("dang_ve") and self._mouse is not None:
                vf = self._to_voxel_f(self._mouse)
                if vf is not None:
                    _, chu = gia_tri_do(d["pts"] + [vf], d["kieu"], rsp, csp)
            if chu and pts_ve:
                if d["kieu"] == "goc" and len(pts_ve) >= 2:
                    vt = pts_ve[1]
                else:
                    vt = QtCore.QPointF((pts_ve[0].x() + pts_ve[-1].x()) / 2,
                                        (pts_ve[0].y() + pts_ve[-1].y()) / 2)
                x, y = vt.x() + 8, vt.y() - 8
                p.setPen(QtGui.QColor(0, 0, 0))
                p.drawText(QtCore.QPointF(x + 1, y + 1), chu)
                p.setPen(mau)
                p.drawText(QtCore.QPointF(x, y), chu)
    def _ve_duong_lat(self, p, rect, rows, cols):
        """Vẽ 2 đường kẻ cho biết vị trí lát cắt của 2 khung còn lại."""
        anh_em = {cv.axis: cv.k for cv in getattr(self.nguon, "canvases", None) or []
                  if cv is not self}
        if not anh_em:
            return
        _, _, _, _, flip = self._hinh_dang()
        # (trục ngang = hàng, trục dọc = cột) của khung này ứng với k của khung nào
        truc_hang, truc_cot = {0: (1, 2), 1: (0, 2), 2: (0, 1)}[self.axis]
        vung = rect.intersected(QtCore.QRectF(self.rect()))
        if truc_hang in anh_em:
            r = anh_em[truc_hang]
            rr = (rows - 1 - r) if flip else r
            y = rect.y() + (rr + 0.5) / rows * rect.height()
            if vung.top() <= y <= vung.bottom():
                p.setPen(QtGui.QPen(QtGui.QColor(*MAU_TRUC[truc_hang], 210), 2))
                p.drawLine(QtCore.QPointF(vung.left(), y), QtCore.QPointF(vung.right(), y))
        if truc_cot in anh_em:
            c = anh_em[truc_cot]
            x = rect.x() + (c + 0.5) / cols * rect.width()
            if vung.left() <= x <= vung.right():
                p.setPen(QtGui.QPen(QtGui.QColor(*MAU_TRUC[truc_cot], 210), 2))
                p.drawLine(QtCore.QPointF(x, vung.top()), QtCore.QPointF(x, vung.bottom()))
    # ── tương tác ────────────────────────────────────────────────────────
    def wheelEvent(self, ev):
        if self.nguon.ct_u8 is None:
            ev.accept()
            return
        delta = ev.angleDelta().y() or ev.angleDelta().x()
        mods = ev.modifiers()
        if mods & QtCore.Qt.KeyboardModifier.AltModifier:
            self._xoay(2.0 if delta > 0 else -2.0)
        elif mods & QtCore.Qt.KeyboardModifier.ControlModifier:
            self._zoom_tai(ev.position(), 1.15 if delta > 0 else 1 / 1.15)
        else:
            self.set_k(self.k + (1 if delta > 0 else -1))
        ev.accept()

    def _xoay(self, delta_deg):
        """Nghiêng mặt phẳng cắt quanh trục vuông góc với khung này."""
        n = self.nguon
        n.goc[self.axis] = float(np.clip(n.goc[self.axis] + delta_deg, -45.0, 45.0))
        self._painting = False
        for cv in getattr(n, "canvases", None) or [self]:
            cv._cache_key = None
            cv.update()

    def _zoom_tai(self, pos, he_so):
        z_moi = float(np.clip(self.zoom * he_so, 1.0, 16.0))
        if abs(z_moi - self.zoom) < 1e-9:
            return
        W, H = max(self.width(), 1), max(self.height(), 1)
        center = QtCore.QPointF(W / 2.0 + self.pan.x(), H / 2.0 + self.pan.y())
        d = pos - center
        ty_le = z_moi / self.zoom
        center_moi = pos - d * ty_le
        self.pan = QtCore.QPointF(center_moi.x() - W / 2.0, center_moi.y() - H / 2.0)
        self.zoom = z_moi
        if self.zoom <= 1.001:
            self.pan = QtCore.QPointF(0.0, 0.0)
        self.update()

    def mouseDoubleClickEvent(self, ev):
        self.zoom = 1.0
        self.pan = QtCore.QPointF(0.0, 0.0)
        if self._dang_xoay():
            self.nguon.goc[:] = [0.0, 0.0, 0.0]
            for cv in getattr(self.nguon, "canvases", None) or [self]:
                cv._cache_key = None
                cv.update()
        self.update()

    def set_k(self, k):
        n = self.nguon
        if n.ct_u8 is None:
            return
        self.k = int(np.clip(k, 0, n.shape[self.axis] - 1))
        n.dong_bo_thanh_truot(self.axis, self.k)
        self.update()
        for cv in getattr(n, "canvases", None) or []:
            if cv is not self:
                cv.update()      # đường kẻ vị trí lát ở khung kia đổi theo

    def _to_voxel(self, pos):
        rect, rows, cols = self._khung_anh()
        if rect.width() <= 0 or rect.height() <= 0:
            return None
        fx = (pos.x() - rect.x()) / rect.width() * cols
        fy = (pos.y() - rect.y()) / rect.height() * rows
        if not (0 <= fx < cols and 0 <= fy < rows):
            return None
        r, c = int(fy), int(fx)
        _, _, _, _, flip = self._hinh_dang()
        if flip:
            r = rows - 1 - r
        return r, c

    def mousePressEvent(self, ev):
        n = self.nguon
        if ev.button() == QtCore.Qt.MouseButton.MiddleButton:
            self._pan_last = ev.position()
            return
        if ev.button() == QtCore.Qt.MouseButton.RightButton:
            # Kéo chuột PHẢI = đổi sáng/tương phản (như phần mềm CT)
            self._wl_last = ev.position()
            return
        if ev.button() == QtCore.Qt.MouseButton.LeftButton and n.ct_u8 is not None:
            if self._che_do_do() is not None and not self._dang_xoay():
                self._them_diem_do(ev.position())
            elif n.che_do_ve() and not self._dang_xoay():
                self._painting = True
                n.bat_dau_net_ve(self.axis, self.k)
                self._ve(ev.position())
            else:
                self._nav = True
                self._dieu_huong(ev.position())
                # báo nhãn dưới con trỏ (chọn vùng thông minh trong danh sách)
                bam = getattr(n, "khi_bam_nhan", None)
                if bam is not None and n.lab is not None and not self._dang_xoay():
                    v = self._to_voxel(ev.position())
                    if v is not None:
                        r, c = v
                        zyx = {0: (self.k, r, c), 1: (r, self.k, c),
                               2: (r, c, self.k)}[self.axis]
                        try:
                            bam(int(n.lab[zyx]))
                        except IndexError:
                            pass

    def _dieu_huong(self, pos):
        """Bấm/kéo chuột trái (chế độ xem): đưa 2 khung kia đến điểm đó."""
        v = self._to_voxel(pos)
        if v is None:
            return
        r, c = v
        dat = {0: {1: r, 2: c}, 1: {0: r, 2: c}, 2: {0: r, 1: c}}[self.axis]
        for cv in getattr(self.nguon, "canvases", None) or []:
            if cv is not self and cv.axis in dat:
                cv.set_k(int(dat[cv.axis]))
        self.update()

    def mouseMoveEvent(self, ev):
        self._mouse = ev.position()
        if getattr(self, "_wl_last", None) is not None:
            d = ev.position() - self._wl_last
            self._wl_last = ev.position()
            n = self.nguon
            if hasattr(n, "dat_cua_so"):
                level, window = n.cua_so
                # kéo ngang: tương phản (phải = tăng), kéo dọc: sáng (lên = sáng hơn)
                n.dat_cua_so(level + d.y() * 0.6, window - d.x() * 1.2)
                if n.khi_doi_cua_so:
                    n.khi_doi_cua_so(*n.cua_so)
                for cv in getattr(n, "canvases", None) or [self]:
                    cv.update()
            return
        if self._pan_last is not None:
            d = ev.position() - self._pan_last
            self._pan_last = ev.position()
            self.pan = QtCore.QPointF(self.pan.x() + d.x(), self.pan.y() + d.y())
        elif self._painting:
            self._ve(ev.position())
        elif self._nav:
            self._dieu_huong(ev.position())
        self.update()   # (khi đang đo: đoạn tạm chạy theo con trỏ)

    def mouseReleaseEvent(self, ev):
        if self._painting:
            ket = getattr(self.nguon, "ket_thuc_net_ve", None)
            if ket is not None:
                ket()
        self._painting = False
        self._nav = False
        self._pan_last = None
        self._wl_last = None

    def leaveEvent(self, ev):
        self._mouse = None
        self.update()

    def _ve(self, pos):
        v = self._to_voxel(pos)
        if v is not None:
            self.nguon.to_tai(self.axis, self.k, v[0], v[1])
