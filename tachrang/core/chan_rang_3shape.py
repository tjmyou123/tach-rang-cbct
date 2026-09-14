#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
chan_rang_3shape.py — GHÉP CHÂN RĂNG THẬT (CBCT) VÀO RĂNG ĐÃ SEGMENT CỦA 3SHAPE ORTHOANALYZER.

Khảo sát 2026-09-08 (Ortho System 2021-1, C:/ProgramData/3Shape/OrthoData/<patient>/<modelset>/):
  - Tooth_<N>.dcm (N = số răng Universal 1-32) là HPS/DCM KHÔNG mã hóa (schema CA):
    Vertices float32 xyz, Facets nén theo chuẩn HIMSA Packed Scan 501, FacetMarks uint32/facet.
    Tọa độ = HỆ TỌA ĐỘ SCAN GỐC (trùng file STL đã nhập) -> dùng thẳng T scan→CBCT của bước ④.
  - Byte cao của FacetMarks: 0x30 = bề mặt scan (thân răng), 0x08 = CHÂN ẢO 3Shape tự sinh,
    0x38 = dải chuyển tiếp quanh cổ răng. Verified: facet 0x08 cách scan ~2.2 mm, 0x30 ~0.08 mm.
  - Models/Tooth_<N>.stl là bản STL cùng lưới (cập nhật kèm để đồng bộ).
  - OrthoModellingTree.3ml (margin, setup, stage) là zip có mật khẩu -> KHÔNG đụng.

Cách làm: bỏ facet chân ảo (0x08) -> còn thân răng 3Shape Y NGUYÊN + đường biên cổ răng;
cắt răng CBCT (đưa về hệ scan) lấy phần dưới đường biên một khe `gap`; khâu 2 đường biên
bằng dải tam giác (zip theo góc quanh trục răng); facet chân mới đánh mark 0x08000000
(cờ "chân") để 3Shape đối xử như chân ảo. Ghi lại Vertices/Facets/FacetMarks vào .dcm
(Facets mã hóa bằng lệnh RESTART_16/RESTART_32 hợp chuẩn), cập nhật Models/*.stl.

LUÔN sao lưu toàn bộ thư mục bệnh nhân trước khi ghi (backup_3shape/<patient>_<time>/).
Dùng (đóng OrthoAnalyzer trước):
  python -m tachrang.core.chan_rang_3shape --model-set "C:/ProgramData/3Shape/OrthoData/<mã-bn>/1"
        --case <tên-ca-CBCT> [-o ket_qua] [--gap 0.4] [--thu]  (--thu: chỉ ghi ra thư mục thử, không đụng 3Shape)
  python -m tachrang.core.chan_rang_3shape --khoi-phuc <thư mục backup>
"""
import argparse
import base64
import json
import re
import shutil
import struct
import sys
import time
from pathlib import Path

import numpy as np

from tachrang.core.ham_lai import _doc_polydata, _pd_sang_numpy, _bien_doi, _numpy_sang_pd, ghi_stl_pd, RE_SCAN_JSON
from tachrang.core.can_scan import liet_ke_rang, RE_FDI

MARK_CHAN = 0x08000000          # cờ "chân răng tự sinh" của 3Shape
RE_TOOTH = re.compile(r"^Tooth_(\d+)\.dcm$", re.I)


# ───────────────────────────── số răng Universal <-> FDI ─────────────────────────────
def universal_sang_fdi(n: int) -> int:
    """Universal 1-16 hàm trên từ phải sang trái (1=18, 8=11, 9=21, 16=28);
    17-32 hàm dưới từ trái sang phải (17=38, 24=31, 25=41, 32=48)."""
    if 1 <= n <= 8:
        return 10 + (9 - n)
    if 9 <= n <= 16:
        return 20 + (n - 8)
    if 17 <= n <= 24:
        return 30 + (25 - n)
    if 25 <= n <= 32:
        return 40 + (n - 24)
    raise ValueError(f"số răng Universal không hợp lệ: {n}")


# ───────────────────────────── đọc / ghi HPS-DCM ─────────────────────────────
def doc_dcm(path: Path):
    """Trả về dict: text (XML gốc), V (N,3) float64, F (M,3) int64, marks (M,) uint32 hoặc None."""
    from hpsdecode import load_hps
    path = Path(path)
    text = path.read_bytes().decode("latin1")
    if "<Schema>CA</Schema>" not in text and "<Schema>CC</Schema>" not in text:
        raise ValueError(f"{path.name}: schema không phải CA/CC (có thể mã hóa) — không xử lý")
    _, mesh = load_hps(str(path))
    V = np.asarray(mesh.vertices, dtype=np.float64)
    F = np.asarray(mesh.faces, dtype=np.int64)
    marks = None
    m = re.search(r"<FacetMarks>([^<]*)</FacetMarks>", text)
    if m and m.group(1).strip():
        mb = base64.b64decode(m.group(1))
        if len(mb) == 4 * len(F):
            marks = np.frombuffer(mb, dtype=np.uint32).copy()
    props = dict(re.findall(r'<Property name="(\w+)" value="([^"]*)"/>', text))
    return {"text": text, "V": V, "F": F, "marks": marks, "props": props}


def dung_lai_tu_stl(path_dcm: Path, ms_dir: Path, nguong_than=0.35):
    """Răng đã bị 3Shape ghi lại dạng CE (mã hóa, vd sau khi làm mịn) → dựng lại từ bản STL
    không mã hóa mà 3Shape ghi kèm cùng lúc (Models/Tooth_N.stl). FacetMarks không để ánh xạ được
    (khác thứ tự facet) nên tái tạo theo hình học: facet có tâm cách bề mặt hàm đã chuẩn bị
    (Maxillary/Mandibular.dcm, cùng hệ) < nguong_than → thân 0x30000000, còn lại chân ảo 0x08000000.
    Khung XML lấy từ chính file CE (phần ngoài binary không mã hóa), đổi sang schema CA."""
    from scipy.spatial import cKDTree
    path_dcm = Path(path_dcm)
    ms_dir = Path(ms_dir)
    stl = ms_dir / "Models" / path_dcm.with_suffix(".stl").name
    if not stl.is_file():
        raise ValueError(f"{path_dcm.name}: mã hóa và không có Models/{stl.name} để dựng lại")
    if abs(stl.stat().st_mtime - path_dcm.stat().st_mtime) > 120:
        raise ValueError(f"{path_dcm.name}: mã hóa; Models/{stl.name} không cùng lần lưu (lệch giờ) — không dám dùng")
    text = path_dcm.read_bytes().decode("latin1")
    props = dict(re.findall(r'<Property name="(\w+)" value="([^"]*)"/>', text))
    fc = re.search(r'facet_count="(\d+)"', text)
    V, F = _pd_sang_numpy(_doc_polydata(stl))
    if fc and int(fc.group(1)) != len(F):
        raise ValueError(f"{path_dcm.name}: STL kèm có {len(F)} facet ≠ {fc.group(1)} trong .dcm — không cùng lưới")
    ham = "Maxillary.dcm" if props.get("Upper", "True") == "True" else "Mandibular.dcm"
    tham = ms_dir / ham
    try:
        d_ham = doc_dcm(tham)
        Vt = d_ham["V"]
    except Exception as e:
        raise ValueError(f"{path_dcm.name}: cần {ham} (hàm đã chuẩn bị) để phân biệt thân/chân nhưng không đọc được: {e}")
    C = V[F].mean(axis=1)
    d, _ = cKDTree(Vt).query(C, k=1)
    marks = np.where(d < nguong_than, 0x30000000, 0x08000000).astype(np.uint32)
    # khung XML: CE -> CA
    text_ca = text.replace("<Schema>CE</Schema>", "<Schema>CA</Schema>")
    text_ca = re.sub(r'<CE version="([^"]*)">', r'<CA version="\1">', text_ca).replace("</CE>", "</CA>")
    text_ca = re.sub(r' check_value="\d+"', "", text_ca)
    if "<FacetMarks>" not in text_ca:
        text_ca = text_ca.replace("</Packed_geometry>", "</Packed_geometry>\n  <FacetMarks></FacetMarks>", 1)
    return {"text": text_ca, "V": V, "F": F, "marks": marks, "props": props, "dung_lai_tu_stl": True,
            "ti_le_than": float((marks == 0x30000000).mean())}


def doc_rang_3shape(path_dcm: Path, ms_dir: Path):
    """Đọc Tooth_N.dcm; nếu CE (mã hóa) thì dựng lại từ STL kèm."""
    try:
        return doc_dcm(path_dcm)
    except ValueError as e:
        if "schema" not in str(e):
            raise
        return dung_lai_tu_stl(path_dcm, ms_dir)


def ma_hoa_facets(F, so_dinh):
    """(Cũ — KHÔNG DÙNG cho 3Shape) mã hóa bằng RESTART_16/32: hợp chuẩn HIMSA nhưng
    OrthoAnalyzer 2021 không hiểu → nối tam giác sai (răng răng cưa). Giữ để tham khảo."""
    F = np.asarray(F, dtype=np.int64)
    if so_dinh < 65536:
        op, fmt = 5, "<HHH"
    else:
        op, fmt = 6, "<III"
    out = bytearray()
    for a, b, c in F:
        out.append(op)
        out += struct.pack(fmt, int(a), int(b), int(c))
    return bytes(out)


def ghi_dcm(text_goc: str, V, F, marks, path_dst: Path):
    """Thay Vertices/Facets/FacetMarks trong XML gốc, giữ mọi thứ khác; ghi file.
    Facets mã hóa bằng đúng bộ lệnh 3Shape (hps_ma_hoa) → đỉnh/facet được đánh số lại.
    Trả về (V_moi, F_moi) đúng như đã ghi (để ghi STL kèm)."""
    from tachrang.core.hps_ma_hoa import ma_hoa_facets_3shape, giai_ma_kiem_tra
    V = np.asarray(V, dtype=np.float64)
    F = np.asarray(F, dtype=np.int64)
    fb, perm, thu_tu, F2 = ma_hoa_facets_3shape(F, len(V))
    F_chk = giai_ma_kiem_tra(fb, len(perm), len(F))
    if not np.array_equal(F_chk, F2):
        raise RuntimeError("mã hóa facets không giải mã lại đúng — không ghi")
    V32 = np.ascontiguousarray(V[perm].astype(np.float32))
    vb = V32.tobytes()
    mb = np.ascontiguousarray(np.asarray(marks, dtype=np.uint32)[thu_tu]).tobytes()
    b64 = lambda b: base64.b64encode(b).decode("ascii")

    def thay_facets(m):
        attrs = m.group(1)
        attrs = re.sub(r'facet_count="\d+"', f'facet_count="{len(F)}"', attrs)
        attrs = re.sub(r'base64_encoded_bytes="\d+"', f'base64_encoded_bytes="{len(fb)}"', attrs)
        return f"<Facets{attrs}>{b64(fb)}</Facets>"

    def thay_vertices(m):
        attrs = m.group(1)
        attrs = re.sub(r'vertex_count="\d+"', f'vertex_count="{len(V32)}"', attrs)
        attrs = re.sub(r'base64_encoded_bytes="\d+"', f'base64_encoded_bytes="{len(vb)}"', attrs)
        return f"<Vertices{attrs}>{b64(vb)}</Vertices>"

    text, n1 = re.subn(r"<Facets([^>]*)>[^<]*</Facets>", thay_facets, text_goc, count=1)
    text, n2 = re.subn(r"<Vertices([^>]*)>[^<]*</Vertices>", thay_vertices, text, count=1)
    text, n3 = re.subn(r"<FacetMarks>[^<]*</FacetMarks>", f"<FacetMarks>{b64(mb)}</FacetMarks>", text, count=1)
    if not (n1 == n2 == 1):
        raise ValueError("Không tìm thấy thẻ Facets/Vertices trong DCM")
    Path(path_dst).write_bytes(text.encode("latin1"))
    return V32.astype(np.float64), F2


# ───────────────────────────── hình học ─────────────────────────────
def _duong_bien(F):
    """Các vòng biên (list các list chỉ số đỉnh, theo chiều cạnh có hướng của facet)."""
    E = np.vstack([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
    co = set(map(tuple, E))
    bien = [(a, b) for a, b in map(tuple, E) if (b, a) not in co]
    nxt = {}
    for a, b in bien:
        nxt.setdefault(a, []).append(b)
    vong, da = [], set()
    for a, b in bien:
        if (a, b) in da:
            continue
        loop, cur, prev = [a], a, None
        while True:
            cands = [x for x in nxt.get(cur, []) if (cur, x) not in da]
            if not cands:
                break
            nx = cands[0]
            da.add((cur, nx))
            if nx == loop[0]:
                break
            loop.append(nx)
            cur = nx
        if len(loop) >= 3:
            vong.append(loop)
    vong.sort(key=len, reverse=True)
    return vong


def _don(V, F):
    dung = np.unique(F)
    mp = -np.ones(len(V), dtype=np.int64)
    mp[dung] = np.arange(len(dung))
    return V[dung], mp[F], mp


def _the_tich_co_dau(V, F):
    a, b, c = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    return float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6.0)


def _nhan_lien_thong_facet(F):
    """Nhãn thành phần liên thông của TỪNG FACET (kề qua cạnh chung)."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    n = len(F)
    E = np.vstack([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
    E = np.sort(E, axis=1)
    fid = np.tile(np.arange(n), 3)
    # gom facet theo cạnh: sắp theo cạnh, cặp liền nhau cùng cạnh → kề
    key = E[:, 0].astype(np.int64) * (E.max() + 1) + E[:, 1]
    o = np.argsort(key, kind="stable")
    key, fid = key[o], fid[o]
    cung = key[1:] == key[:-1]
    i, j = fid[:-1][cung], fid[1:][cung]
    A = coo_matrix((np.ones(len(i)), (i, j)), shape=(n, n))
    _, lab = connected_components(A, directed=False)
    return lab


def _thanh_phan_lon_nhat(V, F):
    lab = _nhan_lien_thong_facet(F)
    top = np.bincount(lab).argmax()
    V2, F2, _ = _don(V, F[lab == top])
    return V2, F2


def _goc_don_dieu(th):
    """Góc dọc theo vòng (theo thứ tự lưới) → tham số tăng đơn điệu [0, tổng)."""
    d = np.diff(th)
    d = (d + np.pi) % (2 * np.pi) - np.pi
    cum = np.concatenate([[0.0], np.cumsum(d)])
    if cum[-1] < 0:
        cum = -cum
    return np.maximum.accumulate(cum)


def _va_lo(V, F, marks, toi_da=80):
    """Vá các vòng biên còn lại bằng hình quạt quanh tâm (thêm 1 đỉnh/lỗ)."""
    vong = [l for l in _duong_bien(F) if len(l) <= toi_da]
    if not vong:
        return V, F, marks, 0
    Vn, Fn = [V], [F]
    off = len(V)
    for l in vong:
        c = V[l].mean(axis=0)
        Vn.append(c[None, :])
        l = np.array(l)
        # cạnh biên có hướng a→b thuộc lưới, tam giác vá phải đi b→a
        Fn.append(np.stack([np.roll(l, -1), l, np.full(len(l), off)], axis=1))
        off += 1
    F2 = np.vstack(Fn)
    marks2 = np.concatenate([marks, np.full(len(F2) - len(F), MARK_CHAN, np.uint32)])
    return np.vstack(Vn), F2, marks2, len(vong)


def _lam_min_co_trong_so(V, F, w, so_lan=10, lam=0.5):
    """Laplace (umbrella) có trọng số từng đỉnh w∈[0,1]: V ← V + lam·w·(trung bình láng giềng − V).
    Đỉnh w=0 cố định tuyệt đối (thân răng 3Shape)."""
    from scipy.sparse import coo_matrix
    n = len(V)
    i = np.concatenate([F[:, 0], F[:, 1], F[:, 2], F[:, 1], F[:, 2], F[:, 0]])
    j = np.concatenate([F[:, 1], F[:, 2], F[:, 0], F[:, 0], F[:, 1], F[:, 2]])
    A = coo_matrix((np.ones(len(i)), (i, j)), shape=(n, n)).tocsr()
    A.data[:] = 1.0
    deg = np.asarray(A.sum(axis=1)).ravel()
    deg[deg == 0] = 1.0
    V = V.copy()
    di = w > 0
    for _ in range(so_lan):
        tb = np.asarray(A @ V) / deg[:, None]
        V[di] += lam * w[di, None] * (tb[di] - V[di])
    return V


def ghep_chan(Va, Fa, marks_a, Vb, Fb, gap=0.4, dai_min=2.0):
    """Va/Fa/marks_a: răng 3Shape (kín, có chân ảo). Vb/Fb: răng CBCT (kín) CÙNG hệ tọa độ.
    Trả về (V, F, marks, thong_tin)."""
    # 1) bỏ KHỐI chân ảo lớn nhất (facet 0x08 liên thông); các facet 0x08 lẻ trong thân giữ lại
    la_chan = (marks_a >> 24) == 0x08
    if not la_chan.any():
        raise ValueError("không có facet chân ảo (mark 0x08) — răng chưa có chân 3Shape?")
    lab = _nhan_lien_thong_facet(Fa[la_chan])
    top = np.bincount(lab).argmax()
    bo = np.zeros(len(Fa), bool)
    bo[np.flatnonzero(la_chan)[lab == top]] = True
    Fa_c, marks_c = Fa[~bo], marks_a[~bo]
    # thân răng phải là 1 khối liên thông: bỏ mảnh lẻ (facet cô lập sau khi bỏ chân ảo)
    lab_c = _nhan_lien_thong_facet(Fa_c)
    giu_c = lab_c == np.bincount(lab_c).argmax()
    Fa_c, marks_c = Fa_c[giu_c], marks_c[giu_c]
    Va_c, Fa_c, _ = _don(Va, Fa_c)
    vong_a = _duong_bien(Fa_c)
    if not vong_a:
        raise ValueError("thân răng 3Shape không có đường biên sau khi bỏ chân ảo")
    La = np.array(vong_a[0])

    # 2) trục răng + hệ tọa độ trụ quanh tâm vòng cổ răng
    c_than = Va_c.mean(axis=0)
    truc = Vb.mean(axis=0) - c_than
    truc /= np.linalg.norm(truc)
    e1 = np.cross(truc, [1.0, 0, 0])
    if np.linalg.norm(e1) < 0.3:
        e1 = np.cross(truc, [0, 1.0, 0])
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(truc, e1)
    tam_vong = Va_c[La].mean(axis=0)

    def toa_do(P):
        d = P - tam_vong
        return (np.einsum("ij,j->i", d, truc),
                np.arctan2(np.einsum("ij,j->i", d, e2), np.einsum("ij,j->i", d, e1)))

    # 3) cắt răng CBCT: giữ phần thấp hơn biên cổ răng một khe gap (theo góc quanh trục).
    #    Biên thân 3Shape răng cưa (ranh giới mark) → lọc trượt vòng để đường cắt chân mượt
    h_a, th_a = toa_do(Va_c[La])
    o = np.argsort(th_a)
    th_s, h_s = th_a[o], h_a[o]
    k = max(3, len(h_s) // 16) | 1
    h_s = np.convolve(np.concatenate([h_s[-k:], h_s, h_s[:k]]), np.ones(k) / k, mode="same")[k:-k]
    th_ext = np.concatenate([th_s - 2 * np.pi, th_s, th_s + 2 * np.pi])
    h_ext = np.concatenate([h_s, h_s, h_s])
    h_b, th_b = toa_do(Vb)
    giu_v = h_b >= np.interp(th_b, th_ext, h_ext) + gap
    giu_f = giu_v[Fb].all(axis=1)
    if giu_f.sum() < 50:
        raise ValueError("phần chân CBCT dưới cổ răng quá nhỏ — kiểm tra căn scan / răng ghép")
    Vb_r, Fb_r, _ = _don(Vb, Fb[giu_f])
    Vb_r, Fb_r = _thanh_phan_lon_nhat(Vb_r, Fb_r)
    vong_b = _duong_bien(Fb_r)
    if not vong_b:
        raise ValueError("chân CBCT sau khi cắt không có đường biên")
    Lb = np.array(vong_b[0])

    # 4) định hướng: 2 mặt hướng ra ngoài ghép kín → vòng biên có hướng phải NGƯỢC chiều quay
    def chieu(V, L):
        _, th = toa_do(V[L])
        d = np.diff(np.concatenate([th, th[:1]]))
        d = (d + np.pi) % (2 * np.pi) - np.pi
        return 1 if d.sum() > 0 else -1
    sa = chieu(Va_c, La)
    if chieu(Vb_r, Lb) == sa:
        Fb_r = Fb_r[:, ::-1].copy()
        Lb = Lb[::-1].copy()
    # duyệt A theo chiều cạnh có hướng, B theo chiều NGƯỢC cạnh có hướng → cùng chiều quay
    Lb = Lb[::-1].copy()
    # B bắt đầu ở đỉnh gần A[0] nhất
    j0 = int(np.argmin(np.linalg.norm(Vb_r[Lb] - Va_c[La[0]], axis=1)))
    Lb = np.roll(Lb, -j0)
    _, th_la = toa_do(Va_c[La])
    _, th_lb = toa_do(Vb_r[Lb])
    # tham số zip = kết họp góc đơn điệu (giữ đúng phía) và chiều dài cung (chia đều tam giác, tránh răng cưa)
    def tham_so(Vl, L, th):
        g = _goc_don_dieu(th)
        g = g / max(g[-1], 1e-9)
        seg = np.linalg.norm(np.diff(Vl[L], axis=0), axis=1)
        s = np.concatenate([[0.0], np.cumsum(seg)])
        s = s / max(s[-1], 1e-9)
        return 0.5 * g + 0.5 * s
    pa = tham_so(Va_c, La, th_la)
    pb = tham_so(Vb_r, Lb, th_lb)

    # 5) khâu (zip): tiến bên có tham số kế tiếp nhỏ hơn
    off = len(Va_c)
    n, m = len(La), len(Lb)
    tri = []
    i = j = 0
    while i < n or j < m:
        pa_next = pa[i + 1] if i + 1 < n else 1.0
        pb_next = pb[j + 1] if j + 1 < m else 1.0
        if i < n and (j >= m or pa_next <= pb_next):
            a0, a1, b = La[i], La[(i + 1) % n], off + Lb[j % m]
            tri.append((a1, a0, b))               # cạnh a0→a1 là cạnh biên A → đi ngược
            i += 1
        else:
            b0, b1, a = off + Lb[j], off + Lb[(j + 1) % m], La[i % n]
            tri.append((b0, b1, a))               # cạnh biên B có hướng là b1→b0 → đi b0→b1
            j += 1
    F_bridge = np.array(tri, dtype=np.int64)
    V = np.vstack([Va_c, Vb_r])
    F = np.vstack([Fa_c, Fb_r + off, F_bridge])
    marks = np.concatenate([marks_c,
                            np.full(len(Fb_r), MARK_CHAN, np.uint32),
                            np.full(len(F_bridge), MARK_CHAN, np.uint32)])
    # 5b) làm mịn mối nối: chân CBCT trong dải `dai_min` mm dưới cổ răng được kéo mềm về biên thân
    #     (Laplace có trọng số giảm dần theo khoảng cách); thân 3Shape giữ nguyên từng đỉnh
    if dai_min > 0:
        h_r, th_r = toa_do(Vb_r)
        dh = h_r - (np.interp(th_r, th_ext, h_ext) + gap)          # ≥ 0: cách đường cắt
        w = np.zeros(len(V))
        w[off:] = np.clip(1.0 - dh / dai_min, 0.0, 1.0)
        # dải chuyển tiếp 3Shape tự sinh (mark 0x38/0x00, không phải mặt scan) cũng được làm mịn;
        # đỉnh chạm bất kỳ facet mặt scan (0x30) thì cố định tuyệt đối.
        # Model set không gắn cờ 0x30 (thân toàn 0x00, vd răng segment trực tiếp không mã hóa)
        # → coi TOÀN BỘ thân là mặt scan, khóa cứng để không làm mịn lem vào mặt nhai.
        la_mat = (marks_c >> 24) == 0x30
        if not la_mat.any():
            la_mat = (marks_c >> 24) != 0x08
        cham_scan = np.zeros(off, bool)
        cham_scan[np.unique(Fa_c[la_mat])] = True
        w[:off] = np.where(cham_scan, 0.0, 0.6)
        V = _lam_min_co_trong_so(V, F, w, so_lan=15, lam=0.6)
    # 6) vá lỗ nhỏ còn lại (vòng biên phụ của thân hoặc chân)
    V, F, marks, so_va = _va_lo(V, F, marks)
    bien_con = _duong_bien(F)
    tt = {"dinh_than": int(len(Va_c)), "facet_than": int(len(Fa_c)),
          "dinh_chan": int(len(Vb_r)), "facet_chan": int(len(Fb_r)), "facet_cau": int(len(F_bridge)),
          "vong_bien_than": len(vong_a), "vong_bien_chan": len(vong_b), "lo_da_va": so_va,
          "bien_con_lai": len(bien_con),
          "the_tich_mm3": round(_the_tich_co_dau(V, F), 1),
          "the_tich_goc_mm3": round(_the_tich_co_dau(Va, Fa), 1)}
    return V, F, marks, tt


# ───────────────────────────── luồng theo model set ─────────────────────────────
def liet_ke_tooth_dcm(ms_dir: Path):
    kq = {}
    for f in sorted(Path(ms_dir).glob("Tooth_*.dcm")):
        m = RE_TOOTH.match(f.name)
        if m:
            kq[int(m.group(1))] = f
    return kq


def tim_T_theo_ham(stl_dir: Path):
    kq = {}
    for j in sorted(Path(stl_dir).glob("*_Scan-ham-*_can-CBCT.json")):
        m = RE_SCAN_JSON.search(j.name)
        if m:
            d = json.loads(j.read_text(encoding="utf-8"))
            kq[m.group(1).lower()] = np.asarray(d["T_scan_sang_cbct"], dtype=float)
    return kq


def sao_luu(ms_dir: Path, goc_backup: Path):
    ms_dir = Path(ms_dir)
    patient_dir = ms_dir.parent
    dst = Path(goc_backup) / f"{patient_dir.name}_{time.strftime('%Y%m%d_%H%M%S')}"
    shutil.copytree(patient_dir, dst)
    (dst / "_NGUON.txt").write_text(str(patient_dir), encoding="utf-8")
    return dst


def khoi_phuc(backup_dir: Path):
    backup_dir = Path(backup_dir)
    nguon = Path((backup_dir / "_NGUON.txt").read_text(encoding="utf-8").strip())
    for f in backup_dir.rglob("*"):
        if f.is_file() and f.name != "_NGUON.txt":
            rel = f.relative_to(backup_dir)
            (nguon / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, nguon / rel)
    return nguon


NGUONG_KHOP = 0.6      # tỉ lệ đỉnh thân 3Shape cách bề mặt răng CBCT < 0.6 mm để coi là cùng răng


def doi_chieu(ms_dir: Path, out_dir: Path, case: str, chi_rang=None, tien_do=None):
    """ĐỐI CHIẾU HÌNH HỌC răng 3Shape ↔ răng CBCT (không ghi gì). Trả về dict:
      T_ham      : {'tren'|'duoi': T scan→CBCT}
      ung_vien   : [{ham, ten, fdi|None, V, F (hệ SCAN), tam}]  — mọi STL răng của hàm đã căn
      rang_3s    : [{tooth, fdi, ham, f, d(dcm), than_V, diem[(khop, j)...] giảm dần,
                     chon j|None, khop, loi?}]
      cung_bn    : bool — ≥50% răng 3Shape trùng bề mặt răng CBCT
      khop_tot   : số răng đã gán tự động
    Điểm khớp = tỉ lệ đỉnh THÂN răng 3Shape (marks ≠ 0x08) cách bề mặt răng CBCT < 0.6 mm;
    gán 1-1 tham lam theo điểm giảm dần, ngưỡng NGUONG_KHOP. Tên file chỉ để báo cáo."""
    from scipy.spatial import cKDTree
    ms_dir = Path(ms_dir)
    stl_dir = Path(out_dir) / "stl" / case
    T_ham = tim_T_theo_ham(stl_dir)
    if not T_ham:
        raise ValueError(f"Ca {case} chưa căn scan (thiếu *_Scan-ham-*_can-CBCT.json)")
    rang = liet_ke_rang(stl_dir)
    ung_vien = []
    for h, files in rang.items():
        if h not in T_ham:
            continue
        Ti = np.linalg.inv(T_ham[h])
        for f in files:
            V, F = _pd_sang_numpy(_doc_polydata(f))
            V = _bien_doi(V, Ti)
            m = RE_FDI.search(f.stem)
            ung_vien.append({"ham": h, "ten": f.name, "fdi": int(m.group(1)) if m else None,
                             "V": V, "F": F, "cay": cKDTree(V), "tam": V.mean(axis=0)})
    if not ung_vien:
        raise ValueError("Không có STL răng đã căn của ca này")
    teeth = liet_ke_tooth_dcm(ms_dir)
    if not teeth:
        raise ValueError(f"Không có Tooth_*.dcm trong {ms_dir} — model set chưa segment?")
    if tien_do:
        tien_do("đối chiếu hình học răng 3Shape ↔ răng CBCT ...")
    ds = []
    for n, f in teeth.items():
        if chi_rang and n not in chi_rang:
            continue
        fdi_3s = universal_sang_fdi(n)
        r = {"tooth": n, "fdi": fdi_3s, "f": f, "d": None, "diem": [], "chon": None, "khop": 0.0}
        try:
            d = doc_rang_3shape(f, ms_dir)
        except ValueError as e:
            r["loi"] = ("3Shape đã lưu răng này dạng MÃ HÓA (CE) và không dựng lại được từ STL kèm: " + str(e)
                        if "mã hóa" in str(e) else str(e))
            ds.append(r)
            continue
        r["d"] = d
        if d.get("dung_lai_tu_stl"):
            r["dung_lai"] = True
        if d["marks"] is None:
            r["loi"] = "không có FacetMarks"
            ds.append(r)
            continue
        than_idx = np.unique(d["F"][(d["marks"] >> 24) != 0x08])
        than = d["V"][than_idx]
        ham = "duoi" if fdi_3s // 10 in (3, 4) else "tren"
        c = than.mean(axis=0)
        diem = []
        for j, u in enumerate(ung_vien):
            if u["ham"] != ham or np.linalg.norm(u["tam"] - c) > 15.0:
                continue
            dist, _ = u["cay"].query(than[::max(1, len(than) // 3000)], k=1)
            diem.append((float((dist < 0.6).mean()), j))
        diem.sort(reverse=True)
        r.update({"ham": ham, "than_V": than, "diem": diem})
        ds.append(r)
    cap = sorted(((dm, i, j) for i, r in enumerate(ds) for dm, j in r["diem"]), reverse=True)
    da_3s, da_cbct = set(), set()
    for dm, i, j in cap:
        if dm < NGUONG_KHOP or i in da_3s or j in da_cbct:
            continue
        ds[i]["chon"] = j
        ds[i]["khop"] = dm
        da_3s.add(i)
        da_cbct.add(j)
    co_diem = [r for r in ds if "loi" not in r]
    if not co_diem:
        so_ce = sum(1 for r in ds if "MÃ HÓA" in r.get("loi", ""))
        if so_ce:
            raise ValueError(
                f"{so_ce}/{len(ds)} răng của model set đã được 3Shape lưu lại dạng MÃ HÓA (schema CE) — "
                "thường xảy ra sau khi mở/lưu Virtual Setup. Phần mềm không đọc được nội dung mã hóa nên "
                "không ghép/kiểm tra lại được model set này.\n"
                "Cách làm: ghép chân NGAY SAU KHI SEGMENT răng (trước khi vào Virtual Setup); hoặc tạo "
                "model set mới từ scan, segment lại rồi ghép. Răng đã ghép trước đó vẫn còn chân trong 3Shape.")
        raise ValueError("Không đọc được răng nào của model set: " + "; ".join(r.get("loi", "?") for r in ds[:3]))
    khop_tot = sum(1 for r in co_diem if r["chon"] is not None)
    cung_bn = bool(co_diem) and khop_tot >= max(1, len(co_diem) // 2)
    for u in ung_vien:
        u.pop("cay", None)
    return {"ms_dir": str(ms_dir), "case": case, "T_ham": T_ham, "ung_vien": ung_vien,
            "rang_3s": ds, "cung_bn": cung_bn, "khop_tot": khop_tot, "so_rang_3s": len(co_diem)}


def ghep_model_set(ms_dir: Path, out_dir: Path, case: str, gap=0.4, thu_dir: Path = None,
                   goc_backup: Path = None, chi_rang=None, tien_do=None, cap_thu_cong=None,
                   dc=None, bo_qua_kiem_bn=False):
    """Ghép chân răng CBCT vào Tooth_N.dcm của model set.
    thu_dir      : nếu có → chỉ ghi ra thư mục này (xem trước, không đụng 3Shape)
    cap_thu_cong : {tooth_n: tên file STL CBCT | None(bỏ qua)} — ghi đè cặp tự động (chế độ thủ công)
    dc           : kết quả doi_chieu() có sẵn (khỏi tính lại)
    Trả về dict báo cáo (ghi kèm _chan_rang_cbct.json vào thư mục đích)."""
    ms_dir = Path(ms_dir)
    if dc is None:
        dc = doi_chieu(ms_dir, out_dir, case, chi_rang, tien_do)
    ung_vien, ds = dc["ung_vien"], dc["rang_3s"]
    ten_toi_j = {u["ten"]: j for j, u in enumerate(ung_vien)}
    if cap_thu_cong:
        for r in ds:
            if r["tooth"] in cap_thu_cong:
                ten = cap_thu_cong[r["tooth"]]
                r["chon"] = ten_toi_j.get(ten) if ten else None
                r["thu_cong"] = True
                if r["chon"] is not None:
                    r["khop"] = next((dm for dm, j in r["diem"] if j == r["chon"]), 0.0)
    if not dc["cung_bn"] and not bo_qua_kiem_bn and not cap_thu_cong:
        best = max((r["diem"][0][0] for r in ds if r["diem"]), default=0.0)
        raise ValueError(
            f"Chỉ {dc['khop_tot']}/{dc['so_rang_3s']} răng 3Shape trùng bề mặt với răng CBCT (khớp tốt nhất "
            f"{best * 100:.0f}%). Model set này KHÔNG cùng scan/bệnh nhân với ca {case}, hoặc scan chưa "
            f"căn đúng (④). Không ghi gì.")
    if (ms_dir / "lock.lck").exists() and thu_dir is None:
        raise ValueError("Model set đang mở trong OrthoAnalyzer (lock.lck) — hãy đóng phần mềm trước")

    backup = None
    if thu_dir is None:
        backup = sao_luu(ms_dir, goc_backup or (Path(out_dir).resolve().parent / "backup_3shape"))
        if tien_do:
            tien_do(f"đã sao lưu vào {backup}")
    dich = Path(thu_dir) if thu_dir else ms_dir
    dich.mkdir(parents=True, exist_ok=True)
    (dich / "Models").mkdir(exist_ok=True)

    ket = []
    da_dung = set()
    for r in ds:
        n, fdi, f, d = r["tooth"], r["fdi"], r["f"], r["d"]
        if "loi" in r:
            ket.append({"tooth": n, "fdi": fdi, "loi": r["loi"]}); continue
        if r["chon"] is None:
            if r.get("thu_cong"):
                ket.append({"tooth": n, "fdi": fdi, "bo_qua": True, "loi": "bỏ qua theo chọn thủ công"})
                continue
            best = r["diem"][0] if r["diem"] else (0.0, None)
            goi = f" (gần nhất: {ung_vien[best[1]]['ten']} khớp {best[0] * 100:.0f}%)" if best[1] is not None else ""
            ket.append({"tooth": n, "fdi": fdi,
                        "loi": f"không có răng CBCT trùng bề mặt thân răng (cần ≥{NGUONG_KHOP * 100:.0f}%){goi} "
                               "— CBCT thiếu răng này hoặc tách/căn chưa đúng"})
            continue
        u = ung_vien[r["chon"]]
        da_dung.add(r["chon"])
        canh_bao = []
        if r.get("dung_lai"):
            canh_bao.append(f"răng 3Shape đã mã hóa (đã làm mịn) → dựng lại từ Models/*.stl, thân/chân "
                            f"phân theo hình học ({d.get('ti_le_than', 0) * 100:.0f}% facet là thân)")
        if r.get("thu_cong"):
            canh_bao.append(f"cặp chọn thủ công (trùng bề mặt {r['khop'] * 100:.0f}%)")
        if u["fdi"] is None:
            canh_bao.append(f"răng CBCT không có số FDI ({u['ten']}) — vẫn ghép vì trùng bề mặt "
                            f"{r['khop'] * 100:.0f}%; nên đổi tên vùng thành FDI{fdi} ở mục ③")
        elif u["fdi"] != fdi:
            canh_bao.append(f"tên FDI lệch: 3Shape răng {n} = FDI{fdi} nhưng file CBCT ghi FDI{u['fdi']} "
                            f"(trùng bề mặt {r['khop'] * 100:.0f}% → ghép theo 3Shape)")
        if "du-doan" in u["ten"]:
            canh_bao.append("số FDI của CBCT là dự đoán (-du-doan)")
        try:
            V, F, marks, tt = ghep_chan(d["V"], d["F"], d["marks"], u["V"], u["F"], gap)
        except Exception as e:
            ket.append({"tooth": n, "fdi": fdi, "cbct": u["ten"], "loi": str(e)}); continue
        V2, F2 = ghi_dcm(d["text"], V, F, marks, dich / f.name)
        ghi_stl_pd(_numpy_sang_pd(V2, F2), dich / "Models" / f"Tooth_{n}.stl")
        tt.update({"tooth": n, "fdi": fdi, "cbct": u["ten"], "fdi_cbct": u["fdi"],
                   "khop": round(r["khop"], 3), "canh_bao": "; ".join(canh_bao) or None})
        ket.append(tt)
        if tien_do:
            tien_do(f"Tooth_{n} (FDI{fdi}) ← {u['ten']} khớp {r['khop'] * 100:.0f}%: thân {tt['facet_than']} + "
                    f"chân {tt['facet_chan']} facet" + (f" | {tt['canh_bao']}" if tt["canh_bao"] else ""))
    thua = [u["ten"] for j, u in enumerate(ung_vien) if j not in da_dung]
    bc = {"model_set": str(ms_dir), "case": case, "gap": gap, "backup": str(backup) if backup else None,
          "thoi_gian": time.strftime("%Y-%m-%d %H:%M:%S"), "nguong_khop": NGUONG_KHOP,
          "thu_cong": bool(cap_thu_cong), "rang": ket, "cbct_khong_dung": thua}
    (dich / "_chan_rang_cbct.json").write_text(json.dumps(bc, ensure_ascii=False, indent=1), encoding="utf-8")
    return bc


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model-set", help="thư mục model set 3Shape (chứa Tooth_N.dcm)")
    ap.add_argument("--case", help="tên ca đã tách + đã căn scan")
    ap.add_argument("-o", "--out", default="ket_qua")
    ap.add_argument("--gap", type=float, default=0.4, help="khe dưới cổ răng nơi bắt đầu chân CBCT (mm)")
    ap.add_argument("--thu", help="thư mục ghi thử (không đụng 3Shape)")
    ap.add_argument("--rang", help="chỉ xử lý các răng Universal này, vd 8,9")
    ap.add_argument("--khoi-phuc", help="khôi phục từ thư mục backup")
    a = ap.parse_args()
    if a.khoi_phuc:
        print("Đã khôi phục về", khoi_phuc(Path(a.khoi_phuc)))
        return
    if not a.model_set or not a.case:
        ap.error("cần --model-set và --case")
    chi = [int(x) for x in a.rang.split(",")] if a.rang else None
    bc = ghep_model_set(Path(a.model_set), Path(a.out), a.case, a.gap,
                        Path(a.thu) if a.thu else None, chi_rang=chi, tien_do=lambda s: print("  ..", s))
    ok = [r for r in bc["rang"] if "loi" not in r]
    loi = [r for r in bc["rang"] if "loi" in r]
    print(f"Xong: {len(ok)} răng ghép, {len(loi)} lỗi" + (f"; backup: {bc['backup']}" if bc["backup"] else ""))
    for r in loi:
        print(f"  [LOI] Tooth_{r['tooth']} (FDI{r['fdi']}): {r['loi']}")


if __name__ == "__main__":
    main()
