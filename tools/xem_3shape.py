# -*- coding: utf-8 -*-
"""Mở 1 file .dcm bằng 3Shape 3D Viewer, chụp màn hình, đóng viewer. Dùng: python xem_3shape.py file.dcm anh.png"""
import subprocess, sys, time
from pathlib import Path
VIEWER = r"C:\Program Files\3Shape\3DViewer\3Shape_3DViewer.exe"
f = Path(sys.argv[1]).resolve()
anh = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else Path("tests/anh/viewer.png").resolve()
cho = float(sys.argv[3]) if len(sys.argv) > 3 else 7.0
subprocess.run(["taskkill", "/IM", "3Shape_3DViewer.exe", "/F"], capture_output=True)
p = subprocess.Popen([VIEWER, str(f)])
time.sleep(cho)
ps = f"""
Add-Type -AssemblyName System.Windows.Forms,System.Drawing
$b=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bmp=New-Object System.Drawing.Bitmap $b.Width,$b.Height
$g=[System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($b.Location,[System.Drawing.Point]::Empty,$b.Size)
$bmp.Save('{anh}')
"""
subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True)
subprocess.run(["taskkill", "/PID", str(p.pid), "/F"], capture_output=True)
print("->", anh)
