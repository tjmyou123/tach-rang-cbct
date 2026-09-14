# -*- coding: utf-8 -*-
"""Kiểm tra ghép theo HÌNH HỌC: (1) ca thật; (2) ca giả: đổi tên FDI11<->FDI21, FDI13 -> Rang-them,
xóa FDI46 để xem cảnh báo/lỗi; (3) model set khác bệnh nhân (dịch T sai) -> phải từ chối."""
import json, shutil, sys
from pathlib import Path
import numpy as np
GOC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GOC))
from tachrang.core import chan_rang_3shape as c3

CASE = "DICOM-000000000024-20220917150728"
MS = GOC / "backup_3shape" / "1222_20260908_163527" / "1"     # răng 3Shape GỐC (chân ảo)
OUT = GOC / "ket_qua"


def tom_tat(bc):
    ok = [r for r in bc["rang"] if "loi" not in r]
    loi = [r for r in bc["rang"] if "loi" in r]
    print(f"  ghép {len(ok)}, lỗi {len(loi)}, CBCT không dùng: {bc['cbct_khong_dung']}")
    for r in ok:
        if r.get("canh_bao"):
            print(f"  [CB] Tooth_{r['tooth']} FDI{r['fdi']} ← {r['cbct']} ({r['khop']*100:.0f}%): {r['canh_bao']}")
    for r in loi:
        print(f"  [LOI] Tooth_{r['tooth']} FDI{r['fdi']}: {r['loi']}")
    khop = [r["khop"] for r in ok]
    if khop:
        print(f"  khớp bề mặt: min {min(khop)*100:.0f}% median {np.median(khop)*100:.0f}%")


print("=== (1) ca thật ===")
bc = c3.ghep_model_set(MS, OUT, CASE, 0.4, thu_dir=GOC / "data_test/3shape_thu/hinh_hoc_1", tien_do=None)
tom_tat(bc)

print("=== (2) ca giả: tên sai / Rang-them / thiếu răng ===")
fake_out = GOC / "data_test/3shape_thu/fake_out"
if fake_out.exists():
    shutil.rmtree(fake_out)
dst = fake_out / "stl" / CASE
dst.mkdir(parents=True)
src = OUT / "stl" / CASE
for f in src.iterdir():
    if f.is_file() and (f.suffix in (".stl", ".json")):
        nm = f.name
        if "FDI46_" in nm:
            continue                                   # thiếu răng 46
        if "FDI11_" in nm:
            nm = nm.replace("FDI11_upper-right-central-incisor", "FDI21_upper-left-central-incisor")
        elif "FDI21_" in nm:
            nm = nm.replace("FDI21_upper-left-central-incisor", "FDI11_upper-right-central-incisor")
        elif "FDI13_" in nm:
            nm = nm.replace("FDI13_upper-right-canine", "Rang-them-ham-tren-1")
        shutil.copy2(f, dst / nm)
bc = c3.ghep_model_set(MS, fake_out, CASE, 0.4, thu_dir=GOC / "data_test/3shape_thu/hinh_hoc_2", tien_do=None)
tom_tat(bc)

print("=== (3) khác bệnh nhân: ma trận căn dịch 6 mm ===")
fake2 = GOC / "data_test/3shape_thu/fake_out2"
if fake2.exists():
    shutil.rmtree(fake2)
shutil.copytree(src, fake2 / "stl" / CASE)
for js in (fake2 / "stl" / CASE).glob("*_can-CBCT.json"):
    d = json.loads(js.read_text(encoding="utf-8"))
    T = np.array(d["T_scan_sang_cbct"]); T[:3, 3] += 6.0
    d["T_scan_sang_cbct"] = T.tolist()
    js.write_text(json.dumps(d), encoding="utf-8")
try:
    c3.ghep_model_set(MS, fake2, CASE, 0.4, thu_dir=GOC / "data_test/3shape_thu/hinh_hoc_3", tien_do=None)
    print("  KHÔNG từ chối — SAI")
except ValueError as e:
    print("  từ chối đúng:", str(e)[:160])
