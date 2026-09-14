# -*- coding: utf-8 -*-
"""Kiểm tra bộ mã hóa HPS kiểu 3Shape: mã hóa lại răng gốc và răng đã ghép, giải mã lại, so lưới."""
import sys, time
from pathlib import Path
from collections import Counter
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tachrang.core.chan_rang_3shape import doc_dcm
from tachrang.core.hps_ma_hoa import ma_hoa_facets_3shape, giai_ma_kiem_tra


def tap_tam_giac(V, F):
    # tập tam giác theo tọa độ (bất biến với hoán vị/nhân bản đỉnh), giữ chiều
    P = V[F]                                  # (M,3,3)
    # xoay vòng để đỉnh nhỏ nhất (theo thứ tự từ điển) đứng đầu
    key = [tuple(map(tuple, np.round(p, 5))) for p in P]
    out = set()
    for a, b, c in key:
        m = min((a, b, c), (b, c, a), (c, a, b))
        out.add(m)
    return out


for f in sys.argv[1:]:
    d = doc_dcm(Path(f))
    V, F = d["V"], d["F"]
    t = time.time()
    fb, perm, thu_tu, F2 = ma_hoa_facets_3shape(F, len(V), tien_do=lambda s: print("   ", s) if "Restart" in s else None)
    dt = time.time() - t
    ops = Counter(fb[i] for i in range(len(fb)))   # xấp xỉ (payload Absolute lẫn vào) — chỉ để nhìn
    F3 = giai_ma_kiem_tra(fb, len(perm), len(F))
    V2 = V[perm]
    ok_dec = np.array_equal(F3, F2)
    same = tap_tam_giac(V, F) == tap_tam_giac(V2, F2)
    print(f"{Path(f).name}: V {len(V)}→{len(perm)} (nhân bản {len(perm)-len(V)}), F {len(F)}={len(F2)}, "
          f"bytes {len(fb)} ({len(fb)/len(F):.2f}/facet), {dt:.1f}s | giải mã lại khớp: {ok_dec} | lưới giống hệt: {same}")
