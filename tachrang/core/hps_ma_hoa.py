#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hps_ma_hoa.py — MÃ HÓA facets theo chuẩn HIMSA Packed Scan (schema CA/CC) bằng ĐÚNG bộ lệnh
mà 3Shape Ortho System tự ghi: Restart(4) 1 lần đầu, VertexList(0), Previous(1), Next(2),
Ignore(3), Absolute16(7), Remove(9). (3Shape KHÔNG hiểu RESTART_16/32, ABSOLUTE_32 →
ghi bằng các lệnh đó thì OrthoAnalyzer nối tam giác sai — bài học 2026-09-08.)

Cách làm: mô phỏng máy trạng thái của bộ giải mã (dùng chính CCSchemaParser của hpsdecode
để chắc chắn cùng ngữ nghĩa), tham lam "mọc vùng" từ tam giác đầu: với cạnh biên hiện tại
(s→e) tìm tam giác chưa mã hóa chứa cạnh (e→s); đỉnh thứ 3 v:
  - v = đầu cạnh trước  → Previous;  v = cuối cạnh sau → Next;
  - v chưa xuất hiện    → VertexList (v nhận chỉ số toàn cục kế tiếp → ta ĐÁNH SỐ LẠI đỉnh);
  - v đã xuất hiện      → Absolute16(v).
Cạnh "chết" (tam giác ngoài đã mã hóa): Remove khi là gai (prev.start == cur.end) hoặc
prev cũng chết; ngược lại Ignore. Sau mỗi lệnh kiểm tra tam giác máy sinh ra == tam giác
định mã hóa. Trả về (bytes, hoán vị đỉnh, thứ tự facet) để ghi lại Vertices/FacetMarks.
"""
import struct
import numpy as np

KIEM_GAI = True      # kiểm tra sau mỗi lệnh rằng danh sách cạnh không có "gai" (chậm hơn, an toàn)


class _May:
    """Bọc CCSchemaParser của hpsdecode làm máy mô phỏng."""

    def __init__(self):
        from hpsdecode.schemas.cc import CCSchemaParser
        self.p = CCSchemaParser()
        self.p._clear()

    @property
    def edges(self):
        return self.p._edge_list

    @property
    def cur(self):
        return self.p._current_edge_idx

    def chay(self, cmd):
        n0 = len(self.p._faces)
        self.p._process_command(cmd, None)
        return self.p._faces[n0:]


def ma_hoa_facets_3shape(F, so_dinh, tien_do=None):
    """F (M,3) int: lưới định hướng nhất quán (kín hoặc hở). Trả về
    (bytes lệnh, perm (N',) chỉ số cũ theo chỉ số mới — N' ≥ N nếu phải nhân bản đỉnh,
     thu_tu (M,) chỉ số facet cũ theo thứ tự ghi, faces_moi (M,3) theo chỉ số mới).
    Đỉnh không thuộc facet nào được xếp cuối. V mới = V[perm]; marks mới = marks[thu_tu]."""
    import hpsdecode.commands as hpc
    F = np.asarray(F, dtype=np.int64)
    M = len(F)
    # 3Shape ghi payload của Absolute16 (opcode 7) luôn 4 byte little-endian, KỂ CẢ lưới nhỏ
    # (hpsdecode gọi là "16-bit opcode but 32-bit payload"). Ghi 2 byte → 3Shape lệch byte,
    # dừng ở Absolute đầu tiên (bài học 2026-09-08: viewer chỉ hiện 63 facet).
    fmt_abs = "<I"

    # cạnh có hướng → facet
    mat = {}
    for fi, (a, b, c) in enumerate(F):
        mat[(a, b)] = fi
        mat[(b, c)] = fi
        mat[(c, a)] = fi
    done = np.zeros(M, bool)
    chi_so = -np.ones(so_dinh, dtype=np.int64)     # cũ → mới
    perm = []                                        # mới → cũ
    thu_tu = []
    out = bytearray()
    may = _May()

    def gan(v):
        chi_so[v] = len(perm)
        perm.append(int(v))

    def moi(v):
        return int(chi_so[v])

    def phat(cmd, fi):
        faces = may.chay(cmd)
        if len(faces) != 1:
            raise RuntimeError("lệnh không sinh đúng 1 facet")
        got = tuple(perm[x] for x in faces[0])          # về chỉ số cũ
        a, b, c = (int(x) for x in F[fi])
        if got not in ((a, b, c), (b, c, a), (c, a, b)):
            raise RuntimeError(f"máy sinh {got} khác facet {(a, b, c)} — lỗi mã hóa")
        done[fi] = True
        thu_tu.append(fi)

    def dinh_thu_3(fi, e, s):
        for x in F[fi]:
            if x != e and x != s:
                return int(x)
        raise RuntimeError("facet suy biến")

    # cũ theo chỉ số mới → cần tra ngược khi đọc cạnh trong máy (máy lưu chỉ số MỚI)
    def cu(i_moi):
        return perm[i_moi]

    con_lai = M
    fi0 = 0
    so_restart = 0
    while con_lai > 0:
        # ── Restart: tam giác hạt giống với 3 đỉnh MỚI (lần đầu luôn được; lần sau phải nhân bản đỉnh)
        while fi0 < M and done[fi0]:
            fi0 += 1
        so_restart += 1
        if so_restart > 1 and tien_do:
            tien_do(f"cảnh báo: Restart phụ #{so_restart} tại facet {fi0}, còn {con_lai} facet (ngữ cảnh 3Shape không dùng)")
        a, b, c = F[fi0]
        for v in (a, b, c):
            if chi_so[v] >= 0:
                # đã có chỉ số → nhân bản đỉnh (mất liên thông cục bộ nhưng hợp lệ)
                perm.append(int(v))
            else:
                gan(v)
        out.append(4)
        phat(hpc.Restart(), fi0)
        con_lai -= 1
        khong_tien = 0
        while con_lai > 0 and len(may.edges) > 0:
            E = may.edges
            n = len(E)
            ci = may.cur
            ce = E[ci]
            pe = E[(ci - 1) % n]
            ne = E[(ci + 1) % n]
            s, e = cu(ce.start), cu(ce.end)
            p, y = cu(pe.start), cu(ne.end)
            fi = mat.get((e, s))
            song = fi is not None and not done[fi]
            if song:
                v = dinh_thu_3(fi, e, s)
                # ngữ cảnh 3Shape thật (phân tích 32-bit): Previous/Next khi n≥5; Remove cả khi có
                # "gai" (207 lần) lẫn không gai (90 lần); hpsdecode giải đúng cả hai → dùng được
                if n >= 5 and p == v and cu(pe.end) == s:
                    out.append(1); phat(hpc.Previous(), fi)
                elif n >= 5 and y == v and cu(ne.start) == e:
                    out.append(2); phat(hpc.Next(), fi)
                elif chi_so[v] < 0:
                    gan(v)
                    out.append(0); phat(hpc.VertexList(), fi)
                else:
                    out.append(7); out += struct.pack(fmt_abs, moi(v))
                    phat(hpc.Absolute16(v=moi(v)), fi)
                con_lai -= 1
                khong_tien = 0
            else:
                gai = pe.start == ce.end
                fpi = mat.get((cu(pe.end), p))
                prev_chet = fpi is None or done[fpi]
                if n > 2 and (gai or prev_chet):
                    out.append(9); may.chay(hpc.Remove())
                    khong_tien = 0
                else:
                    out.append(3); may.chay(hpc.Ignore())
                    khong_tien += 1
                    if khong_tien > n + 2:
                        break                       # kẹt → Restart với đỉnh nhân bản
            if tien_do and (M - con_lai) % 20000 == 0:
                tien_do(f"mã hóa {M - con_lai}/{M}")
    # đỉnh không dùng
    for v in range(so_dinh):
        if chi_so[v] < 0:
            gan(v)
    faces_moi = np.asarray(may.p._faces, dtype=np.int64)
    return bytes(out), np.asarray(perm, dtype=np.int64), np.asarray(thu_tu, dtype=np.int64), faces_moi


def giai_ma_kiem_tra(fb, so_dinh, so_facet):
    """Giải mã lại bằng hpsdecode ÉP chế độ 32-bit (như 3Shape đọc) → (M,3) hoặc ném lỗi."""
    from hpsdecode.schemas.cc import CCSchemaParser, IndexMode
    par = CCSchemaParser()
    par._clear()
    cmds = par._parse_commands(fb, IndexMode.MODE_32BIT)
    for c in cmds:
        par._process_command(c, so_dinh)
    faces = np.asarray(par._faces, dtype=np.int64)
    if len(faces) != so_facet:
        raise RuntimeError(f"giải mã 32-bit ra {len(faces)} facet, mong {so_facet}")
    return faces
