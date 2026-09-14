# -*- coding: utf-8 -*-
"""sua_nhan.py — Thuật toán sửa bản đồ nhãn (tương đương vài hiệu ứng Segment Editor
của 3D Slicer, rút gọn cho răng/xương CBCT). Không phụ thuộc Qt/VTK.

Quy ước chung:
  lab   : numpy int16 (z, y, x) — SỬA TẠI CHỖ
  ct_u8 : numpy uint8 (z, y, x) cùng cỡ, thang 0-255 (ảnh đã cửa sổ)
  sp    : spacing (sx, sy, sz) mm theo thứ tự SimpleITK
Mỗi hàm trả về KetQua(net=[(bbox, bản sao cũ)], nhan={id đã đổi}, so_voxel=±n) để
giao diện đẩy vào ngăn xếp Hoàn tác và dựng lại 3D đúng những vùng bị đụng.
"""

from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage as ndi

_K26 = np.ones((3, 3, 3), bool)


@dataclass
class KetQua:
    net: list = field(default_factory=list)      # [(bbox, patch cũ)]
    nhan: set = field(default_factory=set)       # id nhãn có thay đổi
    so_voxel: int = 0                            # số voxel thêm (+) / bớt (-)
    ghi_chu: str = ""


def _bbox_nhan(lab, i, pad_vox):
    """Hộp bao quanh nhãn i (nới pad_vox mỗi chiều). None nếu nhãn rỗng."""
    slcs = ndi.find_objects((lab == i).astype(np.int8))
    if not slcs or slcs[0] is None:
        return None
    return _noi(slcs[0], pad_vox, lab.shape)


def _noi(slc, pad_vox, shape):
    out = []
    for s, p, n in zip(slc, pad_vox, shape):
        out.append(slice(max(s.start - int(p), 0), min(s.stop + int(p), n)))
    return tuple(out)


def _pad_vox(mm, sp):
    """mm -> số voxel theo (z, y, x)."""
    sz, sy, sx = sp[2], sp[1], sp[0]
    return (int(np.ceil(mm / max(sz, 1e-6))), int(np.ceil(mm / max(sy, 1e-6))),
            int(np.ceil(mm / max(sx, 1e-6))))


def _sampling(sp):
    return (float(sp[2]), float(sp[1]), float(sp[0]))


# ── 1. Lấp theo ngưỡng (Threshold + Islands giới hạn quanh vùng) ──────────────

def lap_theo_nguong(lab, ct_u8, i, nguong, ban_kinh_mm, sp, nguong_cao=255):
    """Thêm vào nhãn i mọi voxel CHƯA có nhãn, đủ sáng (nguong ≤ ct ≤ nguong_cao),
    LIỀN KHỐI với vùng i và cách vùng i không quá ban_kinh_mm.

    Dùng để "vá" chóp chân răng / mảnh xương AI bỏ sót mà không tô tay từng lát:
    khe tối giữa hai răng chặn màu lan sang răng kế, bán kính chặn lan dọc xương.
    """
    kq = KetQua()
    if lab is None or ct_u8 is None:
        return kq
    bb = _bbox_nhan(lab, i, _pad_vox(ban_kinh_mm, sp))
    if bb is None:
        kq.ghi_chu = "vùng rỗng"
        return kq
    sub = lab[bb]
    ct = ct_u8[bb]
    hat = sub == i
    sang = (ct >= nguong) & (ct <= nguong_cao)
    ung_vien = sang & (sub == 0)
    if not ung_vien.any():
        kq.ghi_chu = "không có điểm sáng trống quanh vùng"
        return kq
    # liền khối với hạt giống
    khoi, _ = ndi.label(hat | ung_vien, _K26)
    id_hat = np.unique(khoi[hat])
    id_hat = id_hat[id_hat > 0]
    if id_hat.size == 0:
        return kq
    lien = np.isin(khoi, id_hat) & ung_vien
    # giới hạn khoảng cách tới vùng i
    dist = ndi.distance_transform_edt(~hat, sampling=_sampling(sp))
    chon = lien & (dist <= float(ban_kinh_mm))
    n = int(chon.sum())
    if n == 0:
        kq.ghi_chu = "không có điểm nào trong bán kính"
        return kq
    kq.net.append((bb, sub.copy()))
    sub[chon] = np.int16(i)
    kq.nhan.add(int(i))
    kq.so_voxel = n
    kq.ghi_chu = f"+{n} voxel"
    return kq


# ── 2. Làm mịn một vùng (Smoothing: Gaussian / Median tương tự Slicer) ────────

def lam_min_vung(lab, i, sigma_mm, sp, de_len=False):
    """Làm mượt bề mặt nhãn i bằng Gaussian rồi lấy ngưỡng 0.5 (như Slicer
    'Gaussian smoothing'). Voxel bị bỏ -> 0; voxel thêm CHỈ vào chỗ trống,
    trừ khi de_len=True (được phép lấn sang nhãn khác)."""
    kq = KetQua()
    if lab is None:
        return kq
    pad = _pad_vox(3.0 * sigma_mm + 1.0, sp)
    bb = _bbox_nhan(lab, i, pad)
    if bb is None:
        kq.ghi_chu = "vùng rỗng"
        return kq
    sub = lab[bb]
    mask = (sub == i).astype(np.float32)
    sz, sy, sx = _sampling(sp)
    sig = (sigma_mm / max(sz, 1e-6), sigma_mm / max(sy, 1e-6), sigma_mm / max(sx, 1e-6))
    mem = ndi.gaussian_filter(mask, sigma=sig) > 0.5
    # giữ liền khối lớn nhất? — không: răng nhiều mảnh (ngầm) vẫn phải giữ
    them = mem & (sub != i)
    if not de_len:
        them &= sub == 0
    bot = (~mem) & (sub == i)
    n_them, n_bot = int(them.sum()), int(bot.sum())
    if n_them == 0 and n_bot == 0:
        kq.ghi_chu = "không thay đổi"
        return kq
    kq.net.append((bb, sub.copy()))
    if de_len:
        kq.nhan |= set(int(v) for v in np.unique(sub[them]) if v > 0)
    sub[bot] = 0
    sub[them] = np.int16(i)
    kq.nhan.add(int(i))
    kq.so_voxel = n_them - n_bot
    kq.ghi_chu = f"+{n_them} / -{n_bot} voxel"
    return kq


# ── 3. Mọc từ hạt (Grow from seeds — gán chỗ sáng chưa nhãn cho nhãn gần nhất) ──

def moc_tu_hat(lab, ct_u8, nguong, ban_kinh_mm, sp, chi_nhan=None, bo_nhan=()):
    """Mọi voxel sáng (ct ≥ nguong) chưa có nhãn, liền khối với vùng đã có nhãn và
    cách vùng có nhãn ≤ ban_kinh_mm -> nhận nhãn của vùng GẦN NHẤT (theo mm).

    chi_nhan : chỉ những nhãn này được mọc (None = tất cả)
    bo_nhan  : nhãn không tham gia (vd xương lớn) — vừa không mọc, vừa không bị coi là hạt
    Đây là bản rút gọn của 'Grow from seeds' Slicer: đủ để phủ răng/xương AI thiếu
    mà không cần vẽ hạt giống mới.
    """
    kq = KetQua()
    if lab is None or ct_u8 is None:
        return kq
    tham_gia = lab > 0
    for b in bo_nhan:
        tham_gia &= lab != b
    if chi_nhan is not None:
        m = np.zeros_like(tham_gia)
        for c in chi_nhan:
            m |= lab == c
        tham_gia &= m
    if not tham_gia.any():
        kq.ghi_chu = "không có hạt"
        return kq
    slcs = ndi.find_objects(tham_gia.astype(np.int8))
    bb = _noi(slcs[0], _pad_vox(ban_kinh_mm, sp), lab.shape)
    sub = lab[bb]
    ct = ct_u8[bb]
    hat = tham_gia[bb]
    ung_vien = (ct >= nguong) & (sub == 0)
    if not ung_vien.any():
        kq.ghi_chu = "không còn chỗ sáng trống"
        return kq
    khoi, n_khoi = ndi.label(hat | ung_vien, _K26)
    id_hat = np.unique(khoi[hat])
    id_hat = id_hat[id_hat > 0]
    if id_hat.size == 0 or not (np.isin(khoi, id_hat) & ung_vien).any():
        kq.ghi_chu = "chỗ sáng không chạm hạt nào"
        return kq
    # Xử lý TỪNG KHỐI liền nhau: chỉ nhận nhãn của hạt trong cùng khối
    # (khe tối giữa 2 răng -> răng bên này không bao giờ lấy nhãn răng bên kia)
    hop = ndi.find_objects(khoi)
    cu = sub.copy()
    moi = sub.copy()
    tong = 0
    for cid in id_hat:
        sl = hop[int(cid) - 1]
        if sl is None:
            continue
        mk = khoi[sl] == cid
        h = hat[sl] & mk
        muc = ung_vien[sl] & mk
        if not muc.any():
            continue
        nhan_trong = np.unique(sub[sl][h])
        nhan_trong = nhan_trong[nhan_trong > 0]
        if nhan_trong.size == 1:
            dist = ndi.distance_transform_edt(~h, sampling=_sampling(sp))
            chon = muc & (dist <= float(ban_kinh_mm))
            moi[sl][chon] = nhan_trong[0]
        else:
            dist, idx = ndi.distance_transform_edt(~h, sampling=_sampling(sp),
                                                   return_indices=True)
            chon = muc & (dist <= float(ban_kinh_mm))
            s_sl = sub[sl]
            moi[sl][chon] = s_sl[idx[0][chon], idx[1][chon], idx[2][chon]]
        tong += int(chon.sum())
    if tong == 0:
        kq.ghi_chu = "không có điểm nào trong bán kính"
        return kq
    kq.net.append((bb, cu))
    sub[...] = moi
    doi = moi != cu
    kq.nhan |= set(int(v) for v in np.unique(moi[doi]) if v > 0)
    kq.so_voxel = tong
    kq.ghi_chu = f"+{tong} voxel cho {len(kq.nhan)} vùng"
    return kq


def hoan_tac(lab, kq: KetQua):
    """Trả lab về trước khi áp KetQua (dùng cho test; giao diện có ngăn xếp riêng)."""
    for bb, patch in reversed(kq.net):
        lab[bb] = patch
