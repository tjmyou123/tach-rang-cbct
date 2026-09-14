# -*- coding: utf-8 -*-
"""tao_portable.py — Đóng gói Tách Răng CBCT thành THƯ MỤC PORTABLE chạy độc lập.

Phương án đóng gói (đã chọn sau khi cân nhắc PyInstaller/Nuitka):
  Nhân bản nguyên bộ Python 3.11 ĐÃ CÀI ĐỦ thư viện (torch CUDA, nnU-Net,
  TotalSegmentator, VTK, PySide6, Open3D…) + mã nguồn tachrang + model AI
  → 1 thư mục TachRang_App/ chép sang máy Windows 10/11 x64 khác là chạy ngay
  bằng nháy đúp TachRang.bat — KHÔNG cần cài Python, KHÔNG cần mạng.

  Vì sao không PyInstaller: torch CUDA + nnunetv2 + totalsegmentator + VTK
  nạp module động rất nhiều → exe đóng băng dễ thiếu file, khó vá; trong khi
  Python trên Windows vốn chạy được từ bất kỳ thư mục nào (relocatable).
  Cách "python xách tay" là cách các app AI desktop lớn (ComfyUI…) đang dùng,
  và tiến trình con của giao diện (QProcess python -m tachrang.core.pipeline)
  hoạt động y hệt lúc phát triển.

Dùng:
  E:/Python/python.exe dong_goi/tao_portable.py                 # bản đầy đủ
  ... --dich "D:\\TachRang_App"      # đổi nơi xuất (mặc định dong_goi/TachRang_App)
  ... --khong-models                # không kèm model AI (nhẹ, máy đích tự tải lần đầu)
  ... --khong-kiem-tra              # bỏ bước chạy thử sau khi đóng gói
  ... --nen                         # nén kết quả thành .zip để chép đi

Kết quả:
  TachRang_App/
  ├── TachRang.bat            ← nháy đúp để chạy (không hiện cửa sổ đen)
  ├── TachRang_console.bat    ← chạy kèm console để xem lỗi khi cần
  ├── HUONG-DAN.txt
  ├── config.json             ← đổi thư mục models/input/output tại đây
  ├── python/                 ← Python + toàn bộ thư viện (~6 GB)
  ├── tachrang/               ← mã nguồn chương trình
  ├── models/                 ← DentalSegmentator, UniversalLab, totalseg_weights (~1.8 GB)
  └── CBCT_input/  ket_qua/  logs/   ← thư mục làm việc
"""
import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):        # console Windows mặc định cp1252 → in tiếng Việt lỗi
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

GOC = Path(__file__).resolve().parent.parent      # thư mục gốc dự án


def chay(cmd, **kw):
    print("  $", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], **kw)


def robocopy(nguon: Path, dich: Path, loai_dir=(), loai_file=()):
    """Copy nhanh bằng robocopy (đa luồng). Mã thoát 0-7 = thành công."""
    cmd = ["robocopy", str(nguon), str(dich), "/E", "/MT:16", "/NFL", "/NDL", "/NJH", "/NP", "/R:2", "/W:2"]
    if loai_dir:
        cmd += ["/XD", *loai_dir]
    if loai_file:
        cmd += ["/XF", *loai_file]
    rc = subprocess.run(cmd, stdout=subprocess.DEVNULL).returncode
    if rc >= 8:
        raise RuntimeError(f"robocopy {nguon} → {dich} lỗi (mã {rc})")


def kich_thuoc(d: Path) -> float:
    return sum(f.stat().st_size for f in d.rglob("*") if f.is_file()) / 1e9


def main():
    ap = argparse.ArgumentParser(description="Đóng gói TachRang thành thư mục portable")
    ap.add_argument("--dich", default=str(GOC / "dong_goi" / "TachRang_App"))
    ap.add_argument("--python", default=sys.base_prefix,
                    help="Thư mục Python nguồn (mặc định: python đang chạy script này)")
    ap.add_argument("--khong-models", action="store_true", help="không kèm model AI")
    ap.add_argument("--khong-kiem-tra", action="store_true", help="bỏ bước chạy thử")
    ap.add_argument("--nen", action="store_true", help="nén .zip sau khi xong")
    a = ap.parse_args()

    py_nguon = Path(a.python)
    dich = Path(a.dich)
    if not (py_nguon / "python.exe").is_file():
        sys.exit(f"[LOI] Không thấy python.exe trong {py_nguon}")
    if dich.exists() and any(dich.iterdir()):
        print(f"[!] {dich} đã có nội dung — sẽ ghi đè/cập nhật (robocopy /E).")
    dich.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    # ── 1. Python + toàn bộ thư viện ──────────────────────────────────
    print(f"[1/6] Chép Python từ {py_nguon} (bỏ __pycache__/.pyc/Doc/Tools/include/libs)…")
    robocopy(py_nguon, dich / "python",
             loai_dir=["__pycache__", "Doc", "Tools", "include", "libs", "tcl"],
             loai_file=["*.pyc", "*.pdb"])
    # DLL VC++ runtime: máy đích có thể CHƯA cài VC++ Redistributable → torch/VTK/PySide6
    # sẽ "DLL load failed". Chép app-local (cạnh python.exe — Microsoft cho phép) từ System32.
    sys32 = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32"
    thieu = []
    for d in ("msvcp140.dll", "msvcp140_1.dll", "msvcp140_2.dll", "msvcp140_atomic_wait.dll",
              "msvcp140_codecvt_ids.dll", "vcruntime140.dll", "vcruntime140_1.dll",
              "vcruntime140_threads.dll", "concrt140.dll", "vcomp140.dll"):
        if (sys32 / d).is_file():
            shutil.copy2(sys32 / d, dich / "python" / d)
        else:
            thieu.append(d)
    if thieu:
        print(f"    [!] System32 máy này thiếu {thieu} — máy đích nên cài VC++ Redistributable x64.")
    # User site-packages (AppData\Roaming\Python\...): pip đôi khi cài gói vào đây
    # (vd typing_extensions torch cần!) → PHẢI gộp vào, nếu không máy đích thiếu module.
    r = subprocess.run([str(py_nguon / "python.exe"), "-c",
                        "import site; print(site.USER_SITE if site.ENABLE_USER_SITE else '')"],
                       capture_output=True, text=True)
    user_site = Path(r.stdout.strip()) if r.stdout.strip() else None
    if user_site and user_site.is_dir():
        print(f"    + gộp user site-packages: {user_site} (chỉ chép file còn thiếu)")
        cmd = ["robocopy", str(user_site), str(dich / "python" / "Lib" / "site-packages"),
               "/E", "/XC", "/XN", "/XO",      # không ghi đè file đã có (site chính ưu tiên)
               "/MT:16", "/NFL", "/NDL", "/NJH", "/NP", "/R:2", "/W:2",
               "/XD", "__pycache__", "/XF", "*.pyc", "*.pdb"]
        if subprocess.run(cmd, stdout=subprocess.DEVNULL).returncode >= 8:
            raise RuntimeError("robocopy user site-packages lỗi")

    # ── 2. Mã nguồn ───────────────────────────────────────────────────
    print("[2/6] Chép mã nguồn tachrang/ …")
    robocopy(GOC / "tachrang", dich / "tachrang", loai_dir=["__pycache__"], loai_file=["*.pyc"])
    shutil.copy2(GOC / "requirements.txt", dich / "requirements.txt")

    # ── 3. Model AI ───────────────────────────────────────────────────
    if a.khong_models:
        print("[3/6] BỎ QUA model AI (--khong-models) — máy đích sẽ tự tải lần đầu (cần mạng).")
    else:
        print("[3/6] Chép model AI …")
        for ten in ("DentalSegmentator", "UniversalLab"):
            src = GOC / "models" / ten
            if src.is_dir():
                robocopy(src, dich / "models" / ten)
        ts = Path.home() / ".totalsegmentator"
        if ts.is_dir():
            robocopy(ts, dich / "models" / "totalseg_weights")
        else:
            print("    [!] Không thấy ~/.totalsegmentator — máy đích sẽ tự tải weights teeth/cranio.")

    # ── 4. Cấu hình + thư mục làm việc ────────────────────────────────
    print("[4/6] Ghi cấu hình + launcher …")
    (dich / "config.json").write_text(
        '{\n "models_dir": "models",\n "input_dir": "CBCT_input",\n'
        ' "output_dir": "ket_qua",\n "logs_dir": "logs"\n}\n', encoding="utf-8")
    for d in ("CBCT_input", "ket_qua", "logs"):
        (dich / d).mkdir(exist_ok=True)

    # ── 5. Launcher ───────────────────────────────────────────────────
    (dich / "TachRang.bat").write_text(
        "@echo off\r\n"
        "rem Tach Rang CBCT - nhay dup de chay\r\n"
        "cd /d \"%~dp0\"\r\n"
        "set TOTALSEG_HOME_DIR=%~dp0models\\totalseg_weights\r\n"
        "start \"\" \"%~dp0python\\pythonw.exe\" -m tachrang\r\n", encoding="ascii")
    (dich / "TachRang_console.bat").write_text(
        "@echo off\r\n"
        "rem Ban chay kem console de xem loi truc tiep\r\n"
        "cd /d \"%~dp0\"\r\n"
        "set TOTALSEG_HOME_DIR=%~dp0models\\totalseg_weights\r\n"
        "\"%~dp0python\\python.exe\" -m tachrang\r\n"
        "pause\r\n", encoding="ascii")
    (dich / "HUONG-DAN.txt").write_text(
        "TÁCH RĂNG CBCT — bản portable\n"
        "==============================\n"
        "1. Chép NGUYÊN thư mục này sang máy Windows 10/11 64-bit (nên để ổ có ≥20GB trống).\n"
        "2. Nháy đúp TachRang.bat để mở chương trình.\n"
        "   - Lần đầu Windows có thể hỏi SmartScreen → More info → Run anyway.\n"
        "   - Muốn xem log trực tiếp khi gặp lỗi: chạy TachRang_console.bat.\n"
        "3. Máy có card NVIDIA (driver mới) sẽ tự dùng GPU; không có thì chạy CPU (chậm hơn).\n"
        "   - Có card NVIDIA nhưng CHƯA cài driver: app vẫn chạy (CPU) và sẽ nhắc ngay trong log;\n"
        "     cài driver tại nvidia.com/drivers rồi mở lại app là tự chuyển GPU (không cần cài lại app).\n"
        "4. Ảnh CBCT đặt vào CBCT_input\\, kết quả ra ket_qua\\ (đổi trong config.json nếu muốn).\n"
        "5. Ghép chân răng 3Shape: máy cần cài 3Shape OrthoAnalyzer, dữ liệu ở C:\\ProgramData\\3Shape\\OrthoData.\n"
        "6. Cập nhật phiên bản: chỉ cần thay thư mục tachrang\\ bằng bản mới.\n", encoding="utf-8")

    # ── 6. Chạy thử ───────────────────────────────────────────────────
    if a.khong_kiem_tra:
        print("[6/6] BỎ QUA chạy thử (--khong-kiem-tra).")
    else:
        print("[6/6] Chạy thử bản đã đóng gói …")
        py = dich / "python" / "python.exe"
        env = {**os.environ, "TOTALSEG_HOME_DIR": str(dich / "models" / "totalseg_weights"),
               "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}   # giống env GUI đặt cho tiến trình con
        doc = dict(capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        r1 = chay([py, "-m", "tachrang", "--gpu-probe"], cwd=dich, env=env, **doc)
        print(f"    gpu-probe → {r1.stdout.strip()!r} (0=CPU, 1=GPU)")
        r2 = chay([py, "-m", "tachrang.core.pipeline", "--help"], cwd=dich, env=env, **doc)
        ok2 = r2.returncode == 0 and "usage" in ((r2.stdout or "") + (r2.stderr or "")).lower()
        print(f"    pipeline --help → {'OK' if ok2 else 'LOI:' + ((r2.stderr or r2.stdout or '')[-400:])}")
        r3 = chay([py, "-c", "import PySide6, vtk, SimpleITK, open3d, hpsdecode, scipy, skimage; print('OK')"],
                  cwd=dich, env=env, **doc)
        print(f"    import thư viện GUI/3D → {r3.stdout.strip() or r3.stderr[-400:]}")
        if r1.stdout.strip() not in ("0", "1") or not ok2 or r3.stdout.strip() != "OK":
            sys.exit("[LOI] Chạy thử KHÔNG đạt — xem thông báo phía trên.")

    print(f"\n✔ XONG sau {time.time()-t0:.0f}s — {dich}")
    print(f"  Kích thước: {kich_thuoc(dich):.1f} GB")
    if a.nen:
        print("  Đang nén .zip (lâu)…")
        z = shutil.make_archive(str(dich), "zip", root_dir=dich.parent, base_dir=dich.name)
        print(f"  → {z} ({Path(z).stat().st_size/1e9:.1f} GB)")
    print("  Chép nguyên thư mục sang máy khác và nháy đúp TachRang.bat.")


if __name__ == "__main__":
    main()
