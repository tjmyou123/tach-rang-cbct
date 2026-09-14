# -*- coding: utf-8 -*-
"""Build bộ cài đặt TachRang_Setup.exe từ thư mục portable TachRang_App.

Cách dùng:
    E:\\Python\\python.exe dong_goi\\tao_setup.py

Yêu cầu:
  - Đã build thư mục portable: dong_goi/tao_portable.py  →  dong_goi/TachRang_App
  - Đã cài Inno Setup 6 (winget install -e --id JRSoftware.InnoSetup)

Kết quả: dong_goi/Output/TachRang_Setup_<phiên bản>.exe (+ các file .bin đi kèm
do bộ cài > 2.1 GB phải chia lát — khi phát hành phải chép đủ exe + bin).
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

GOC = Path(__file__).resolve().parent          # dong_goi/
APP = GOC / "TachRang_App"
ISS = GOC / "tachrang_setup.iss"
ICO = GOC / "tachrang.ico"


def tao_icon(duong_dan: Path) -> None:
    """Vẽ icon răng trắng trên nền xanh ngọc bằng Pillow (đa cỡ 16→256)."""
    from PIL import Image, ImageDraw

    n = 256
    anh = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    ve = ImageDraw.Draw(anh)
    # nền vuông bo góc
    ve.rounded_rectangle((8, 8, n - 8, n - 8), radius=52, fill=(15, 118, 110, 255))
    # thân răng: elip lớn (crown) + 2 chân dạng viên nang
    ve.ellipse((58, 50, 198, 152), fill=(255, 255, 255, 255))
    ve.rounded_rectangle((84, 104, 122, 202), radius=19, fill=(255, 255, 255, 255))
    ve.rounded_rectangle((134, 104, 172, 202), radius=19, fill=(255, 255, 255, 255))
    # rãnh nhỏ giữa mặt nhai
    ve.ellipse((118, 56, 138, 76), fill=(15, 118, 110, 255))
    anh.save(duong_dan, sizes=[(256, 256), (48, 48), (32, 32), (16, 16)])
    print(f"  đã vẽ icon: {duong_dan}")


def tim_iscc() -> Path:
    """Tìm ISCC.exe của Inno Setup 6 ở các vị trí quen thuộc."""
    ung_vien = [
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe",
    ]
    tren_path = shutil.which("iscc")
    if tren_path:
        ung_vien.insert(0, Path(tren_path))
    for p in ung_vien:
        if p.is_file():
            return p
    raise SystemExit("Không tìm thấy ISCC.exe — cài bằng: winget install -e --id JRSoftware.InnoSetup")


def kich_thuoc_gb(thu_muc: Path) -> float:
    tong = sum(f.stat().st_size for f in thu_muc.rglob("*") if f.is_file())
    return tong / 1024**3


def main() -> None:
    if not APP.is_dir() or not (APP / "python" / "python.exe").is_file():
        raise SystemExit(f"Chưa có thư mục portable {APP} — chạy tao_portable.py trước.")
    if not ISS.is_file():
        raise SystemExit(f"Thiếu kịch bản {ISS}")

    print(f"[1/3] Icon…")
    if not ICO.is_file():
        tao_icon(ICO)
    else:
        print(f"  dùng icon sẵn có: {ICO}")
    # kèm icon vào bản portable để người dùng tự tạo shortcut nếu muốn
    shutil.copy2(ICO, APP / "tachrang.ico")

    iscc = tim_iscc()
    print(f"[2/3] Biên dịch bộ cài (nguồn {kich_thuoc_gb(APP):.2f} GB — sẽ mất nhiều phút)…")
    print(f"  {iscc}")
    kq = subprocess.run(
        [str(iscc), str(ISS)],
        cwd=str(GOC),
        text=True, encoding="utf-8", errors="replace",
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    # ISCC in rất nhiều dòng "Compressing …" — chỉ giữ phần cuối + dòng lỗi
    dong = (kq.stdout or "").splitlines()
    loc = [d for d in dong if "error" in d.lower() or "warning" in d.lower()]
    print("\n".join(loc + dong[-6:]))
    if kq.returncode != 0:
        raise SystemExit(f"ISCC lỗi (mã {kq.returncode})")

    print("[3/3] Kết quả:")
    out = GOC / "Output"
    tong = 0
    for f in sorted(out.glob("TachRang_Setup*")):
        tong += f.stat().st_size
        print(f"  {f.name}  {f.stat().st_size / 1024**3:.2f} GB")
    print(f"  tổng: {tong / 1024**3:.2f} GB — khi phát hành phải chép ĐỦ file .exe và mọi file .bin")


if __name__ == "__main__":
    main()
