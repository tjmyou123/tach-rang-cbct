#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ham_lai.py — XUẤT "HÀM LAI" ĐỂ NHẬP VÀO 3SHAPE ORTHOANALYZER (model set thứ 2).

Mục đích: OrthoAnalyzer chỉ di chuyển bề mặt răng mà nó đã segment. Muốn chân răng
THẬT (từ CBCT) đi theo răng khi kéo, mesh nhập vào phải chứa sẵn chân răng.
Hàm lai = scan gốc (nướu giữ nguyên, ĐÃ KHOÉT một vành quanh mỗi răng) + mỗi răng
là một vỏ kín: thân răng CBCT được "bám" (chiếu) lên bề mặt scan, chân răng CBCT
giữ nguyên. Toàn bộ nằm trong HỆ TỌA ĐỘ CỦA SCAN GỐC (T^-1), nên khớp cắn giữ nguyên.
File scan gốc KHÔNG bị sửa; kết quả ghi vào stl/<ca>/ham-lai/.

Thuật toán (numpy + scipy cKDTree + VTK):
  1) đọc scan; đọc răng của hàm, đưa về hệ scan bằng T^-1 (T = scan→CBCT đã căn ④);
  2) BÁM THÂN: đỉnh răng CBCT cách bề mặt scan < bam_mm và pháp tuyến cùng hướng
     (|cos| > goc_bam) → chiếu lên mặt phẳng tiếp tuyến của scan tại điểm gần nhất;
  3) KHOÉT NƯỚU: bỏ tam giác scan có đỉnh cách răng CBCT < khe_mm (thân răng scan
     cũ và một vành nướu quanh cổ răng) → chân răng "mọc" qua lỗ;
  4) ghép scan-đã-khoét + các răng → STL nhị phân + JSON số liệu.

Dùng (từ thư mục gốc dự án):
  python -m tachrang.core.ham_lai --case <tên-ca-CBCT> [-o ket_qua]
        [--ham auto|tren|duoi] [--scan-tren f.stl] [--scan-duoi f.stl]
        [--khe 0.8] [--bam 0.4]
"""
import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np

from tachrang.core.can_scan import liet_ke_rang

RE_SCAN_JSON = re.compile(r"_Scan-ham-(tren|duoi)_can-CBCT\.json$", re.I)


# ───────────────────────────── VTK <-> numpy ─────────────────────────────
def _doc_polydata(path: Path):
    import vtk
    ext = Path(path).suffix.lower()
    rd = {".stl": vtk.vtkSTLReader, ".ply": vtk.vtkPLYReader,
          ".obj": vtk.vtkOBJReader}.get(ext)
    if rd is None:
        raise ValueError(f"Định dạng chưa hỗ trợ: {ext}")
    r = rd()
    r.SetFileName(str(path))
    r.Update()
    tri = vtk.vtkTriangleFilter()
    tri.SetInputData(r.GetOutput())
    tri.Update()
    cl = vtk.vtkCleanPolyData()
    cl.SetInputData(tri.GetOutput())
    cl.Update()
    pd = cl.GetOutput()
    if pd.GetNumberOfPoints() == 0 or pd.GetNumberOfCells() == 0:
        raise ValueError(f"Không đọc được mesh: {path}")
    return pd


def _pd_sang_numpy(pd):
    from vtk.util.numpy_support import vtk_to_numpy
    V = vtk_to_numpy(pd.GetPoints().GetData()).astype(np.float64)
    F = vtk_to_numpy(pd.GetPolys().GetData()).reshape(-1, 4)[:, 1:].astype(np.int64)
    return V, F


def _numpy_sang_pd(V, F):
    import vtk
    from vtk.util.numpy_support import numpy_to_vtk, numpy_to_vtkIdTypeArray
    pd = vtk.vtkPolyData()
    pts = vtk.vtkPoints()
    pts.SetData(numpy_to_vtk(np.ascontiguousarray(V, dtype=np.float64), deep=True))
    pd.SetPoints(pts)
    cells = np.hstack([np.full((len(F), 1), 3, dtype=np.int64), F.astype(np.int64)])
    ca = vtk.vtkCellArray()
    ca.SetCells(len(F), numpy_to_vtkIdTypeArray(np.ascontiguousarray(cells.ravel()), deep=True))
    pd.SetPolys(ca)
    return pd


def _phap_tuyen_dinh(V, F):
    """Pháp tuyến đỉnh (trung bình pháp tuyến mặt có trọng số diện tích), đơn vị."""
    n_f = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    N = np.zeros_like(V)
    for k in range(3):
        np.add.at(N, F[:, k], n_f)
    l = np.linalg.norm(N, axis=1)
    l[l == 0] = 1.0
    return N / l[:, None]


def _bien_doi(V, T):
    T = np.asarray(T, dtype=float)
    return V @ T[:3, :3].T + T[:3, 3]


def ghi_stl_pd(pd, path: Path):
    """Ghi STL nhị phân qua file tạm ASCII rồi di chuyển (đường dẫn có dấu)."""
    import vtk
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix=".stl")
    os.close(fd)
    w = vtk.vtkSTLWriter()
    w.SetFileName(tmp)
    w.SetFileTypeToBinary()
    w.SetInputData(pd)
    w.Write()
    if not Path(tmp).is_file() or Path(tmp).stat().st_size == 0:
        Path(tmp).unlink(missing_ok=True)
        raise ValueError(f"Không ghi được STL: {path}")
    shutil.move(tmp, str(path))
    return path


# ───────────────────────────── lõi thuật toán ─────────────────────────────
def bam_than_rang(Vr, Fr, cay_scan, Vs, Ns, bam_mm=0.4, goc_bam=0.6):
    """Chiếu các đỉnh răng CBCT nằm sát bề mặt scan lên scan (bám thân răng).
    - |h| < 0.2 mm: bám luôn (dời quá nhỏ, khỏi xét pháp tuyến — tránh răng cưa ở rìa cắn);
    - |h| < bam_mm và pháp tuyến cùng hướng (|cos| > goc_bam): bám;
    - vành đỉnh chưa bám kề đỉnh đã bám: làm mịn Laplace 3 lượt để không có bậc.
    Trả về (V mới, mặt nạ đỉnh đã bám, độ dời trung bình mm)."""
    Nr = _phap_tuyen_dinh(Vr, Fr)
    d, idx = cay_scan.query(Vr, k=1)
    ns = Ns[idx]
    cos = np.abs(np.einsum("ij,ij->i", Nr, ns))
    # khoảng cách thật tới mặt phẳng tiếp tuyến (chính xác hơn khoảng cách tới đỉnh)
    h = np.einsum("ij,ij->i", Vr - Vs[idx], ns)
    gan = d < bam_mm * 1.5
    chon = gan & ((np.abs(h) < 0.2) | ((np.abs(h) < bam_mm) & (cos > goc_bam)))
    V2 = Vr.copy()
    V2[chon] = Vr[chon] - h[chon, None] * ns[chon]
    doi = float(np.abs(h[chon]).mean()) if chon.any() else 0.0
    if chon.any() and not chon.all():
        from scipy.sparse import coo_matrix
        n = len(Vr)
        i = np.concatenate([Fr[:, 0], Fr[:, 1], Fr[:, 2], Fr[:, 1], Fr[:, 2], Fr[:, 0]])
        j = np.concatenate([Fr[:, 1], Fr[:, 2], Fr[:, 0], Fr[:, 0], Fr[:, 1], Fr[:, 2]])
        A = coo_matrix((np.ones(len(i)), (i, j)), shape=(n, n)).tocsr()
        A.data[:] = 1.0
        deg = np.asarray(A.sum(axis=1)).ravel()
        deg[deg == 0] = 1.0
        ke_bam = np.asarray(A @ chon.astype(float)).ravel() > 0
        vanh = ke_bam & ~chon
        for _ in range(3):
            tb = np.asarray(A @ V2) / deg[:, None]
            V2[vanh] = tb[vanh]
    return V2, chon, doi


def khoet_nuou(Vs, Fs, cay_rang, khe_mm=0.8):
    """Bỏ tam giác scan có đỉnh nào cách răng CBCT < khe_mm. Trả về (F còn, số bỏ)."""
    d, _ = cay_rang.query(Vs, k=1)
    gan = d < khe_mm
    bo = gan[Fs].any(axis=1)
    return Fs[~bo], int(bo.sum())


def _don_dinh(V, F):
    """Bỏ đỉnh không còn được tam giác nào dùng, đánh số lại."""
    dung = np.unique(F)
    map_ = -np.ones(len(V), dtype=np.int64)
    map_[dung] = np.arange(len(dung))
    return V[dung], map_[F]


def bo_manh_vun(V, F, dien_tich_min_mm2=4.0):
    """Bỏ các mảnh scan rời có diện tích < dien_tich_min_mm2 (thân răng scan còn sót
    sau khi khoét, nhiễu). Trả về (F còn, số mảnh bỏ, số mảnh còn)."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    n = len(V)
    i = np.concatenate([F[:, 0], F[:, 1], F[:, 2]])
    j = np.concatenate([F[:, 1], F[:, 2], F[:, 0]])
    A = coo_matrix((np.ones(len(i)), (i, j)), shape=(n, n))
    _, nhan = connected_components(A, directed=False)
    nhan_f = nhan[F[:, 0]]
    dt = 0.5 * np.linalg.norm(np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]]), axis=1)
    dt_manh = np.bincount(nhan_f, weights=dt, minlength=nhan.max() + 1)
    giu = dt_manh[nhan_f] >= dien_tich_min_mm2
    co = dt_manh > 0
    return F[giu], int((co & (dt_manh < dien_tich_min_mm2)).sum()), int((dt_manh >= dien_tich_min_mm2).sum())


def tao_ham_lai(scan_path: Path, T_scan_sang_cbct, rang_files, out_path: Path,
                khe_mm=0.3, bam_mm=0.4, goc_bam=0.6, tien_do=None):
    """Tạo 1 hàm lai. Trả về dict số liệu."""
    from scipy.spatial import cKDTree
    import vtk
    scan_path = Path(scan_path)
    Ti = np.linalg.inv(np.asarray(T_scan_sang_cbct, dtype=float))
    if tien_do:
        tien_do(f"đọc scan {scan_path.name} ...")
    Vs, Fs = _pd_sang_numpy(_doc_polydata(scan_path))
    Ns = _phap_tuyen_dinh(Vs, Fs)
    cay_scan = cKDTree(Vs)

    rang = []           # [(tên, V, F)]
    so_bam, so_dinh, tong_doi = 0, 0, []
    for i, f in enumerate(rang_files, 1):
        if tien_do:
            tien_do(f"bám thân răng {i}/{len(rang_files)}: {f.stem.split('_', 1)[-1]}")
        Vr, Fr = _pd_sang_numpy(_doc_polydata(f))
        Vr = _bien_doi(Vr, Ti)                           # CBCT → hệ scan
        V2, chon, doi = bam_than_rang(Vr, Fr, cay_scan, Vs, Ns, bam_mm, goc_bam)
        so_bam += int(chon.sum())
        so_dinh += len(Vr)
        if chon.any():
            tong_doi.append(doi)
        rang.append((f.stem, V2, Fr))

    if tien_do:
        tien_do("khoét nướu quanh răng ...")
    V_all = np.vstack([r[1] for r in rang])
    Fs2, so_bo = khoet_nuou(Vs, Fs, cKDTree(V_all), khe_mm)
    Fs2, manh_bo, manh_con = bo_manh_vun(Vs, Fs2)
    Vs2, Fs2 = _don_dinh(Vs, Fs2)

    if tien_do:
        tien_do("ghép và ghi STL ...")
    app = vtk.vtkAppendPolyData()
    app.AddInputData(_numpy_sang_pd(Vs2, Fs2))
    for _, V, F in rang:
        app.AddInputData(_numpy_sang_pd(V, F))
    app.Update()
    nrm = vtk.vtkPolyDataNormals()
    nrm.SetInputData(app.GetOutput())
    nrm.SplittingOff()
    nrm.ConsistencyOff()
    nrm.Update()
    ghi_stl_pd(nrm.GetOutput(), out_path)
    return {
        "file": str(out_path), "scan": str(scan_path),
        "so_rang": len(rang), "rang": [r[0] for r in rang],
        "tam_giac_scan": int(len(Fs)), "tam_giac_scan_bo": so_bo,
        "tam_giac_scan_con": int(len(Fs2)),
        "manh_scan_bo": manh_bo, "manh_scan_con": manh_con,
        "dinh_rang": so_dinh, "dinh_rang_da_bam": so_bam,
        "ti_le_bam": round(so_bam / max(so_dinh, 1), 3),
        "do_doi_bam_trung_binh_mm": round(float(np.mean(tong_doi)), 3) if tong_doi else 0.0,
        "khe_mm": khe_mm, "bam_mm": bam_mm, "goc_bam": goc_bam,
        "T_cbct_sang_scan": Ti.tolist(),
    }


# ───────────────────────────── luồng theo ca ─────────────────────────────
def tim_scan_da_can(stl_dir: Path):
    """{'tren': (scan_path, T), 'duoi': ...} từ các *_Scan-ham-*_can-CBCT.json."""
    kq = {}
    for j in sorted(Path(stl_dir).glob("*_Scan-ham-*_can-CBCT.json")):
        m = RE_SCAN_JSON.search(j.name)
        if not m:
            continue
        d = json.loads(j.read_text(encoding="utf-8"))
        kq[m.group(1).lower()] = (Path(d.get("scan", "")), np.asarray(d["T_scan_sang_cbct"]))
    return kq


def xuat_ham_lai_ca(out_dir: Path, case: str, ham="auto", scan_tren=None, scan_duoi=None,
                    khe_mm=0.3, bam_mm=0.4, goc_bam=0.6, dich: Path = None, tien_do=None):
    """Xuất hàm lai cho 1 ca (1 hoặc 2 hàm). Trả về list dict (mỗi hàm 1 dict)."""
    stl_dir = Path(out_dir) / "stl" / case
    if not stl_dir.is_dir():
        raise ValueError(f"Không có thư mục kết quả {stl_dir}")
    ds = liet_ke_rang(stl_dir)
    da_can = tim_scan_da_can(stl_dir)
    ghi_de = {"tren": scan_tren, "duoi": scan_duoi}
    d_ra = Path(dich) if dich else stl_dir / "ham-lai"
    ket = []
    for h in (("tren", "duoi") if ham == "auto" else (ham,)):
        if not ds[h]:
            if ham != "auto":
                raise ValueError(f"Ca {case} không có STL răng hàm {h}")
            continue
        if h not in da_can:
            if ham != "auto":
                raise ValueError(f"Hàm {h} chưa căn scan (thiếu *_Scan-ham-{h}_can-CBCT.json) — "
                                 f"hãy căn ở bước ④ trước")
            continue
        scan_path, T = da_can[h]
        if ghi_de[h]:
            scan_path = Path(ghi_de[h])
        if not scan_path.is_file():
            raise ValueError(f"Không tìm thấy file scan hàm {h}: {scan_path}\n"
                             f"→ chỉ định lại bằng --scan-{h}")
        out = d_ra / f"{case}_Ham-{h}_lai-3shape.stl"
        kq = tao_ham_lai(scan_path, T, ds[h], out, khe_mm, bam_mm, goc_bam,
                         tien_do=(lambda s, h=h: tien_do(f"[hàm {h}] {s}")) if tien_do else None)
        kq["ham"] = h
        kq["case"] = case
        (out.with_suffix(".json")).write_text(json.dumps(kq, ensure_ascii=False, indent=1),
                                              encoding="utf-8")
        ket.append(kq)
    if not ket:
        raise ValueError(f"Ca {case} chưa có hàm nào vừa có răng vừa đã căn scan")
    return ket


def mo_ta(kq):
    return (f"Hàm {kq['ham']}: {kq['so_rang']} răng, bám thân {kq['ti_le_bam'] * 100:.0f}% đỉnh "
            f"(dời TB {kq['do_doi_bam_trung_binh_mm']:.2f} mm), khoét "
            f"{kq['tam_giac_scan_bo']}/{kq['tam_giac_scan']} tam giác scan, nướu còn "
            f"{kq['manh_scan_con']} mảnh (bỏ {kq['manh_scan_bo']} vụn) → {Path(kq['file']).name}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--case", required=True)
    ap.add_argument("-o", "--out", default="ket_qua")
    ap.add_argument("--ham", default="auto", choices=["auto", "tren", "duoi"])
    ap.add_argument("--scan-tren", help="file scan hàm trên (mặc định lấy từ json đã căn)")
    ap.add_argument("--scan-duoi", help="file scan hàm dưới")
    ap.add_argument("--khe", type=float, default=0.3,
                    help="khoét scan cách răng CBCT dưới ngưỡng này (mm); nhỏ = nướu liền, lớn = khe rõ")
    ap.add_argument("--bam", type=float, default=0.4, help="ngưỡng bám thân răng lên scan (mm)")
    ap.add_argument("--dich", help="thư mục ghi (mặc định stl/<ca>/ham-lai)")
    a = ap.parse_args()
    ket = xuat_ham_lai_ca(Path(a.out), a.case, a.ham, a.scan_tren, a.scan_duoi,
                          a.khe, a.bam, dich=a.dich, tien_do=lambda s: print("  ..", s))
    for kq in ket:
        print(mo_ta(kq))


if __name__ == "__main__":
    main()
