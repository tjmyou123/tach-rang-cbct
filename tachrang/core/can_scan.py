#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
can_scan.py — CĂN TỰ ĐỘNG scan hàm (IOS: STL/PLY/OBJ) với răng đã tách từ CBCT.

Ý tưởng: scan chỉ có THÂN răng (+ nướu), CBCT có cả chân. Ta lấy phần THÂN của
răng CBCT (phía mặt nhai) làm đích, đưa scan về khớp bằng:
  1) căn thô toàn cục: FPFH + RANSAC (Open3D), dự phòng PCA thử 4 hướng lật;
  2) căn tinh: ICP điểm–mặt phẳng nhiều tầng (2 → 0.3 mm) với hàm mất mát bền
     (Tukey) để bỏ qua nướu / nhiễu kim loại / răng thiếu.
Kết quả: ma trận 4×4 scan→CBCT, số liệu chất lượng, và các file xuất:
  - <scan>_can-CBCT.stl         : scan đã đưa về hệ tọa độ CBCT (cùng hệ STL đã tách)
  - <scan>_can-CBCT.json        : ma trận + số liệu
  - stl/<ca>/he-toa-do-scan/    : (tùy chọn) toàn bộ STL của ca đưa sang hệ scan

Dùng độc lập (từ thư mục gốc dự án):
  python -m tachrang.core.can_scan --scan ham_tren.stl --case LE-DINH-LY-1967-DICOM -o ket_qua [--ham auto|tren|duoi] [--xuat-nguoc]
"""
import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np

RE_FDI = re.compile(r"fdi[ _-]?(\d\d)", re.I)


# ───────────────────────────── đọc / chọn dữ liệu ─────────────────────────────
def _mesh_vtk_sang_o3d(path: Path):
    """Đọc STL/PLY/OBJ bằng VTK (chịu được đường dẫn có dấu tiếng Việt, STL nhị
    phân lẫn ASCII, header lạ) rồi chuyển sang Open3D."""
    import vtk
    from vtk.util.numpy_support import vtk_to_numpy
    import open3d as o3d
    ext = path.suffix.lower()
    rd = {".stl": vtk.vtkSTLReader, ".ply": vtk.vtkPLYReader,
          ".obj": vtk.vtkOBJReader}.get(ext)
    if rd is None:
        raise ValueError(f"Định dạng scan chưa hỗ trợ: {ext} (dùng STL/PLY/OBJ)")
    r = rd()
    r.SetFileName(str(path))
    r.Update()
    pd = r.GetOutput()
    if pd is None or pd.GetNumberOfPoints() == 0 or pd.GetNumberOfCells() == 0:
        raise ValueError(f"Không đọc được mesh: {path}")
    tri = vtk.vtkTriangleFilter()
    tri.SetInputData(pd)
    tri.Update()
    pd = tri.GetOutput()
    pts = vtk_to_numpy(pd.GetPoints().GetData()).astype(np.float64)
    cells = vtk_to_numpy(pd.GetPolys().GetData()).reshape(-1, 4)[:, 1:]
    m = o3d.geometry.TriangleMesh(o3d.utility.Vector3dVector(pts),
                                  o3d.utility.Vector3iVector(cells.astype(np.int32)))
    return m


def ghi_stl(m, path: Path):
    """Ghi mesh Open3D ra STL nhị phân; đi qua file tạm (đường dẫn ASCII) rồi
    di chuyển để không lỗi khi thư mục kết quả có dấu tiếng Việt."""
    import shutil
    import tempfile
    import open3d as o3d
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    m.compute_triangle_normals()
    fd, tmp = tempfile.mkstemp(suffix=".stl")
    import os
    os.close(fd)
    ok = o3d.io.write_triangle_mesh(tmp, m, write_ascii=False)
    if not ok or not Path(tmp).is_file() or Path(tmp).stat().st_size == 0:
        Path(tmp).unlink(missing_ok=True)
        raise ValueError(f"Không ghi được STL: {path}")
    shutil.move(tmp, str(path))
    return path


def doc_mesh(path: Path):
    """Đọc mesh scan. Open3D lỗi với đường dẫn có ký tự ngoài ASCII trên Windows
    (UnicodeDecodeError từ pybind) và một số STL header lạ -> ưu tiên VTK."""
    import open3d as o3d
    path = Path(path)
    m = None
    try:
        m = _mesh_vtk_sang_o3d(path)
    except Exception:
        m = None
    if m is None or m.is_empty():
        try:
            m = o3d.io.read_triangle_mesh(str(path))
        except Exception as e:                      # UnicodeDecodeError, RuntimeError...
            raise ValueError(f"Không đọc được mesh {path.name}: {e}") from e
    if m is None or m.is_empty():
        raise ValueError(f"Không đọc được mesh: {path}")
    m.remove_duplicated_vertices()
    m.remove_degenerate_triangles()
    return m


def ham_cua_file(stem: str):
    """'tren' / 'duoi' / None theo tên file STL răng đã tách."""
    s = stem.lower()
    if "rang-ngam" in s:
        return None                  # răng ngầm không có trong scan
    m = RE_FDI.search(s)
    if m:
        q = int(m.group(1)) // 10
        if q in (1, 2):
            return "tren"
        if q in (3, 4):
            return "duoi"
    if "ham-tren" in s or "upper" in s and "teeth" in s:
        return "tren"
    if "ham-duoi" in s or "lower" in s and "teeth" in s:
        return "duoi"
    return None


def liet_ke_rang(stl_dir: Path):
    """{'tren': [Path...], 'duoi': [Path...]} các STL răng của ca."""
    ds = {"tren": [], "duoi": []}
    for f in sorted(stl_dir.glob("*.stl")):
        if "_can-CBCT" in f.stem or "he-toa-do-scan" in str(f.parent):
            continue
        h = ham_cua_file(f.stem)
        if h:
            ds[h].append(f)
    return ds


def huong_mat_nhai(rang_tren, rang_duoi, ham):
    """Vectơ đơn vị từ chân → mặt nhai của hàm `ham`.
    Có cả 2 hàm: hướng từ tâm hàm này sang tâm hàm kia. Thiếu: dùng trục z
    (CBCT: z tăng lên phía đầu → hàm trên mặt nhai hướng -z, hàm dưới +z)."""
    def tam(fs):
        pts = []
        for f in fs:
            m = doc_mesh(f)
            pts.append(np.asarray(m.vertices).mean(axis=0))
        return np.mean(pts, axis=0) if pts else None

    t_tren = tam(rang_tren) if rang_tren else None
    t_duoi = tam(rang_duoi) if rang_duoi else None
    if t_tren is not None and t_duoi is not None:
        d = (t_duoi - t_tren) if ham == "tren" else (t_tren - t_duoi)
        n = float(np.linalg.norm(d))
        if n > 1.0:
            return d / n
    return np.array([0.0, 0.0, -1.0 if ham == "tren" else 1.0])


def than_rang_cbct(files, huong, ti_le=0.45, voxel=0.25):
    """Đám mây điểm phần THÂN (phía mặt nhai, `ti_le` chiều cao răng) của các
    răng CBCT — mục tiêu để scan bám vào. Trả về (pcd, mesh gộp)."""
    import open3d as o3d
    gop = o3d.geometry.TriangleMesh()
    for f in files:
        m = doc_mesh(f)
        v = np.asarray(m.vertices)
        t = v @ huong
        nguong = t.max() - ti_le * (t.max() - t.min())
        giu = t >= nguong
        m.remove_vertices_by_mask(~giu)
        gop += m
    if len(gop.vertices) == 0:
        raise ValueError("Không có thân răng CBCT để căn")
    pcd = gop.sample_points_uniformly(number_of_points=max(20000, len(gop.vertices)))
    pcd = pcd.voxel_down_sample(voxel)
    pcd.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=voxel * 4, max_nn=30))
    return pcd, gop


def scan_thanh_diem(mesh, voxel=0.25):
    import open3d as o3d
    pcd = mesh.sample_points_uniformly(number_of_points=max(40000, len(mesh.vertices)))
    pcd = pcd.voxel_down_sample(voxel)
    pcd.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=voxel * 4, max_nn=30))
    return pcd


# ───────────────────────────── căn thô ─────────────────────────────
def _fpfh(pcd, voxel):
    import open3d as o3d
    p = pcd.voxel_down_sample(voxel)
    p.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=voxel * 2, max_nn=30))
    f = o3d.pipelines.registration.compute_fpfh_feature(
        p, o3d.geometry.KDTreeSearchParamHybrid(radius=voxel * 5, max_nn=100))
    return p, f


def can_tho_ransac(src, dst, voxel=0.6):
    import open3d as o3d
    s, fs = _fpfh(src, voxel)
    d, fd = _fpfh(dst, voxel)
    dist = voxel * 1.5
    res = o3d.pipelines.registration.registration_ransac_based_on_feature_matching(
        s, d, fs, fd, True, dist,
        o3d.pipelines.registration.TransformationEstimationPointToPoint(False), 3,
        [o3d.pipelines.registration.CorrespondenceCheckerBasedOnEdgeLength(0.9),
         o3d.pipelines.registration.CorrespondenceCheckerBasedOnDistance(dist)],
        o3d.pipelines.registration.RANSACConvergenceCriteria(200000, 0.999))
    return np.asarray(res.transformation), float(res.fitness)


def _pca_frame(pts):
    c = pts.mean(axis=0)
    u, s, vt = np.linalg.svd(pts - c, full_matrices=False)
    R = vt.T                           # cột = trục chính
    if np.linalg.det(R) < 0:
        R[:, 2] *= -1
    return c, R


def can_tho_pca(src, dst):
    """Đưa trục chính scan về trục chính đích; thử 4 hướng lật hợp lệ."""
    ps, pd = np.asarray(src.points), np.asarray(dst.points)
    cs, Rs = _pca_frame(ps)
    cd, Rd = _pca_frame(pd)
    ung = []
    for lat in ((1, 1, 1), (1, -1, -1), (-1, 1, -1), (-1, -1, 1)):
        Rl = Rd @ np.diag(lat) @ Rs.T
        T = np.eye(4)
        T[:3, :3] = Rl
        T[:3, 3] = cd - Rl @ cs
        ung.append(T)
    return ung


# ───────────────────────────── căn tinh ─────────────────────────────
def icp_nhieu_tang(src, dst, T0, tang=(2.0, 1.0, 0.5, 0.3)):
    import open3d as o3d
    T = np.array(T0, dtype=np.float64)
    for d in tang:
        loss = o3d.pipelines.registration.TukeyLoss(k=d)
        est = o3d.pipelines.registration.TransformationEstimationPointToPlane(loss)
        res = o3d.pipelines.registration.registration_icp(
            src, dst, d, T, est,
            o3d.pipelines.registration.ICPConvergenceCriteria(
                relative_fitness=1e-7, relative_rmse=1e-7, max_iteration=60))
        T = np.asarray(res.transformation)
    return T


def chat_luong(src, dst, T, nguong_khop=0.3, max_d=1.0):
    """Khoảng cách scan→thân răng CBCT sau căn: median/p90 phần khớp, tỉ lệ khớp."""
    import open3d as o3d
    s = o3d.geometry.PointCloud(src)
    s.transform(T)
    d = np.asarray(s.compute_point_cloud_distance(dst))
    khop = d < max_d
    if khop.sum() == 0:
        return {"ti_le_khop": 0.0, "median_mm": 99.0, "p90_mm": 99.0,
                "ti_le_duoi_0p3": 0.0, "so_diem": int(len(d))}
    dk = d[khop]
    return {"ti_le_khop": float(khop.mean()),
            "median_mm": float(np.median(dk)),
            "p90_mm": float(np.percentile(dk, 90)),
            "ti_le_duoi_0p3": float((dk < nguong_khop).mean()),
            "so_diem": int(len(d))}


def diem_so(q):
    """Điểm để so 2 phương án căn: nhiều điểm khớp + sai số nhỏ."""
    return q["ti_le_khop"] * q["ti_le_duoi_0p3"] / max(q["median_mm"], 0.02)


def can_mot_ham(scan_pcd, dst_pcd, tien_do=None):
    """Căn scan vào thân răng CBCT của 1 hàm. Trả về (T, chất lượng, cách căn thô)."""
    ung_vien = []
    if tien_do:
        tien_do("căn thô FPFH + RANSAC ...")
    try:
        T_r, fit = can_tho_ransac(scan_pcd, dst_pcd)
        ung_vien.append(("ransac", T_r))
    except Exception:
        pass
    for T_p in can_tho_pca(scan_pcd, dst_pcd):
        ung_vien.append(("pca", T_p))
    best = None
    for i, (cach, T0) in enumerate(ung_vien, 1):
        if tien_do:
            tien_do(f"căn tinh ICP phương án {i}/{len(ung_vien)} ({cach}) ...")
        T = icp_nhieu_tang(scan_pcd, dst_pcd, T0)
        q = chat_luong(scan_pcd, dst_pcd, T)
        if best is None or diem_so(q) > diem_so(best[1]):
            best = (T, q, cach)
        # RANSAC đã khớp rất tốt (trung vị < 0.2 mm, >50% điểm < 0.3 mm) → khỏi thử PCA
        if cach == "ransac" and q["median_mm"] < 0.2 and q["ti_le_duoi_0p3"] > 0.5 \
                and q["ti_le_khop"] > 0.4:
            if tien_do:
                tien_do("RANSAC + ICP đã khớp tốt, bỏ qua các phương án dự phòng")
            break
    return best


# ───────────────────────────── luồng chính ─────────────────────────────
def can_scan_voi_ca(scan_path: Path, out_dir: Path, case: str, ham="auto",
                    xuat_nguoc=False, tien_do=None):
    """Căn scan với ca đã tách. Trả về dict kết quả (đường dẫn file, ma trận, số liệu)."""
    import open3d as o3d
    # Cảnh báo "Too few correspondences after mutual filter" của RANSAC là vô hại
    # (tự fallback) nhưng khi chạy pythonw nó bật cửa sổ vtkOutputWindow -> tắt
    o3d.utility.set_verbosity_level(o3d.utility.VerbosityLevel.Error)
    scan_path = Path(scan_path)
    stl_dir = Path(out_dir) / "stl" / case
    ds = liet_ke_rang(stl_dir)
    if not ds["tren"] and not ds["duoi"]:
        raise ValueError(f"Ca {case} chưa có STL răng để căn")
    if tien_do:
        tien_do(f"đọc scan {scan_path.name} ...")
    scan_mesh = doc_mesh(scan_path)
    scan_pcd = scan_thanh_diem(scan_mesh)

    ket = []
    for h in (("tren", "duoi") if ham == "auto" else (ham,)):
        if not ds[h]:
            continue
        if tien_do:
            tien_do(f"dựng thân răng CBCT hàm {h} ({len(ds[h])} răng) ...")
        huong = huong_mat_nhai(ds["tren"], ds["duoi"], h)
        dst_pcd, _ = than_rang_cbct(ds[h], huong)
        T, q, cach = can_mot_ham(scan_pcd, dst_pcd, tien_do)
        ket.append((h, T, q, cach))
    if not ket:
        raise ValueError("Không có răng của hàm cần căn")
    h, T, q, cach = max(ket, key=lambda k: diem_so(k[2]))

    # Xuất scan về hệ CBCT
    scan_c = o3d.geometry.TriangleMesh(scan_mesh)
    scan_c.transform(T)
    scan_c.compute_triangle_normals()
    scan_c.compute_vertex_normals()
    ten = f"{case}_Scan-ham-{h}_can-CBCT.stl"
    f_stl = stl_dir / ten
    ghi_stl(scan_c, f_stl)
    thong_tin = {"case": case, "scan": str(scan_path), "ham": h, "cach_can_tho": cach,
                 "T_scan_sang_cbct": np.asarray(T).tolist(), "chat_luong": q,
                 "so_phuong_an": len(ket),
                 "cac_ham_thu": {k[0]: k[2] for k in ket}}
    f_json = stl_dir / f"{case}_Scan-ham-{h}_can-CBCT.json"
    f_json.write_text(json.dumps(thong_tin, ensure_ascii=False, indent=1), encoding="utf-8")

    xuat = []
    if xuat_nguoc:
        xuat = xuat_sang_he_scan(stl_dir, T, scan_path, tien_do=tien_do)
    thong_tin["file_scan_can"] = str(f_stl)
    thong_tin["file_json"] = str(f_json)
    thong_tin["xuat_nguoc"] = [str(p) for p in xuat]
    return thong_tin


def xuat_sang_he_scan(stl_dir: Path, T, scan_path=None, dich: Path = None,
                      chon=None, tien_do=None):
    """Đưa các STL của ca (răng/xương/xoang...) SANG HỆ TỌA ĐỘ SCAN bằng T^-1
    (T = ma trận scan→CBCT đã căn). Dùng để mở chung với file scan GỐC trong CAD.

    dich : thư mục ghi (mặc định stl/<ca>/he-toa-do-scan/)
    chon : danh sách Path STL cần xuất (mặc định: mọi STL của ca trừ *_can-CBCT)
    Trả về list Path đã ghi. Ghi thêm T_cbct_sang_scan.json vào thư mục đích.
    """
    stl_dir = Path(stl_dir)
    T = np.asarray(T, dtype=float)
    Ti = np.linalg.inv(T)
    d_nguoc = Path(dich) if dich else stl_dir / "he-toa-do-scan"
    d_nguoc.mkdir(parents=True, exist_ok=True)
    files = list(chon) if chon else [f for f in sorted(stl_dir.glob("*.stl"))
                                     if "_can-CBCT" not in f.stem]
    xuat = []
    for i, f in enumerate(files, 1):
        if tien_do:
            tien_do(f"xuất sang hệ scan {i}/{len(files)}: {f.name}")
        m = doc_mesh(f)
        m.transform(Ti)
        m.compute_triangle_normals()
        m.compute_vertex_normals()
        ghi_stl(m, d_nguoc / f.name)
        xuat.append(d_nguoc / f.name)
    (d_nguoc / "T_cbct_sang_scan.json").write_text(
        json.dumps({"T_cbct_sang_scan": Ti.tolist(), "T_scan_sang_cbct": T.tolist(),
                    "scan": str(scan_path) if scan_path else "",
                    "files": [p.name for p in xuat]}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    return xuat


def mo_ta_chat_luong(q):
    """Câu tiếng Việt ngắn cho bác sĩ."""
    med, p90, tl = q["median_mm"], q["p90_mm"], q["ti_le_khop"]
    if med < 0.15 and tl > 0.45:
        muc = "RẤT TỐT"
    elif med < 0.3 and tl > 0.3:
        muc = "TỐT"
    elif med < 0.5:
        muc = "TẠM — nên kiểm tra lại trong 3D"
    else:
        muc = "KÉM — có thể sai hàm / scan thiếu răng / nhiễu kim loại"
    return (f"{muc}: sai số trung vị {med:.2f} mm, 90% điểm dưới {p90:.2f} mm, "
            f"{tl * 100:.0f}% bề mặt scan bám được vào răng CBCT")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scan", required=True, help="file scan hàm (STL/PLY/OBJ)")
    ap.add_argument("--case", required=True, help="tên ca đã tách (thư mục trong stl/)")
    ap.add_argument("-o", "--out", default="ket_qua", help="thư mục kết quả")
    ap.add_argument("--ham", default="auto", choices=["auto", "tren", "duoi"])
    ap.add_argument("--xuat-nguoc", action="store_true",
                    help="xuất thêm toàn bộ STL của ca sang hệ tọa độ scan")
    a = ap.parse_args()
    kq = can_scan_voi_ca(Path(a.scan), Path(a.out), a.case, a.ham, a.xuat_nguoc,
                         tien_do=lambda s: print("  ..", s))
    print(f"Hàm: {kq['ham']} (căn thô: {kq['cach_can_tho']})")
    print(mo_ta_chat_luong(kq["chat_luong"]))
    print("Scan đã căn:", kq["file_scan_can"])
    if kq["xuat_nguoc"]:
        print(f"Đã xuất {len(kq['xuat_nguoc'])} STL sang hệ scan")


if __name__ == "__main__":
    main()
