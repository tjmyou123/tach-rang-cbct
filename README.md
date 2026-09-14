# TachRang — Tách răng tự động từ ảnh CBCT

Ứng dụng Windows tách từng chiếc răng (kèm xương hàm trên/dưới, ống thần kinh) từ ảnh chụp
**CBCT nha khoa (DICOM)** bằng AI, xuất **STL** cho phần mềm CAD/in 3D, và **ghép chân răng
thật vào model set 3Shape OrthoAnalyzer** (thay chân răng ảo bằng chân răng tái tạo từ CBCT
mà giữ nguyên mặt scan/khớp cắn).

Toàn bộ giao diện tiếng Việt, chạy hoàn toàn **trên máy của bạn** — dữ liệu bệnh nhân không
rời khỏi máy.

---

## 1. Tải về & cài đặt (người dùng)

Vào trang **[Releases](../../releases/latest)** và chọn một trong hai:

### Cách A — Bộ cài đặt (khuyên dùng)
1. Tải **đủ 4 file** về cùng một thư mục:
   `TachRang_Setup_1.0.0.exe` + `TachRang_Setup_1.0.0-1.bin` + `-2.bin` + `-3.bin`
   (bộ cài 4,2 GB phải chia lát — thiếu 1 file .bin là không cài được).
2. Nháy đúp file **.exe** → chọn thành phần muốn cài → Install.
   - Lần đầu Windows có thể hỏi SmartScreen: **More info → Run anyway**.
   - Không cần quyền Admin; mặc định cài vào `%LocalAppData%\Programs\TachRang`,
     có thể đổi sang ổ khác (cần ~8 GB trống, nên chừa ≥20 GB).
3. Mở **TachRang** từ Start Menu / Desktop.
4. Gỡ cài đặt: Settings → Apps → TachRang (kết quả và cấu hình của bạn được giữ lại).

### Cách B — Bản portable (không cần cài)
Dành cho máy không muốn chạy bộ cài: nhận thư mục `TachRang_App` qua USB/ổ cứng từ người
phát hành (7,7 GB — vượt giới hạn file của GitHub nên không có trên Releases), hoặc tự build
từ mã nguồn bằng `python dong_goi/tao_portable.py`. Giải nén/chép vào ổ có ≥20 GB trống rồi
nháy đúp **`TachRang.bat`**. Muốn xem log lỗi trực tiếp thì chạy `TachRang_console.bat`.

### Yêu cầu máy
| Thành phần | Tối thiểu |
|---|---|
| Hệ điều hành | Windows 10/11 **64-bit** |
| RAM | 16 GB |
| Ổ trống | 20 GB |
| CPU | Từ ~2013 trở lại (hỗ trợ AVX2) |
| GPU (tuỳ chọn) | NVIDIA + driver mới (CUDA 12.6) — nhanh hơn CPU nhiều lần |

- **Không có GPU / GPU AMD:** vẫn chạy bình thường bằng CPU, chỉ chậm hơn.
- **Có card NVIDIA nhưng chưa cài driver:** app vẫn chạy (CPU) và sẽ nhắc ngay trong log —
  cài driver tại [nvidia.com/drivers](https://www.nvidia.com/drivers) rồi mở lại app là tự
  chuyển sang GPU, **không cần cài lại app**.

---

## 2. Sử dụng

### Tách răng từ CBCT
1. Mở app → bấm **Chọn thư mục DICOM** (hoặc bỏ thư mục ca chụp vào `CBCT_input\`).
2. Ảnh hiện ngay trên 3 mặt cắt. Bấm **Tách răng** — chế độ `auto` tự chọn GPU/CPU
   và cấu hình phù hợp với máy.
3. Xong, kết quả tự hiển thị trong khung 3D:
   - Từng răng đánh số **FDI** (11–48), xương hàm trên/dưới, ống thần kinh.
   - File STL nằm trong `ket_qua\stl\<tên ca>\` — mở được bằng mọi phần mềm CAD/in 3D.
4. Tab **Sửa nhãn**: lấp lỗ theo ngưỡng, làm mịn, mọc từ hạt, hoàn tác… nếu muốn tinh chỉnh.

### Ghép chân răng thật vào 3Shape OrthoAnalyzer
> Máy phải cài sẵn 3Shape OrthoAnalyzer (dữ liệu ở `C:\ProgramData\3Shape\OrthoData`).

1. Tách răng ca CBCT tương ứng xong, mở tab **3Shape**.
2. Chọn bệnh nhân/model set — app tự bắt cặp răng 3Shape ↔ răng CBCT, xem trước 3D.
3. Bấm **Ghép**: chân răng ảo được thay bằng chân răng thật từ CBCT;
   **mặt scan giữ nguyên 0 µm** nên khớp cắn không đổi; model mã hoá (schema CE)
   cũng ghép được. Luôn tự **sao lưu** trước khi ghi (`backup_3shape\`),
   có nút khôi phục.
4. Mở lại OrthoAnalyzer để dùng model đã có chân răng thật.

### Cấu hình
`config.json` trong thư mục cài (tự tạo lần đầu):

```json
{
  "models_dir": "models",
  "input_dir": "CBCT_input",
  "output_dir": "ket_qua",
  "logs_dir": "logs"
}
```

---

## 3. Chạy từ mã nguồn (lập trình viên)

```powershell
git clone https://github.com/tjmyou123/tach-rang-cbct.git
cd tach-rang-cbct
python -m venv .venv ; .\.venv\Scripts\Activate.ps1   # Python 3.11
pip install -r requirements.txt
# PyTorch bản CUDA (GPU NVIDIA):
pip install torch --index-url https://download.pytorch.org/whl/cu126
python -m tachrang        # mở giao diện
```

**Model AI** (không nằm trong git — lấy từ bản cài sẵn trong Releases, hoặc tự đặt vào):

```
models/
├── DentalSegmentator/   # model nnU-Net tách răng  (dự án DentalSegmentator)
└── UniversalLab/        # model bổ trợ
```

Trọng số TotalSegmentator (xương sọ–hàm) tự tải về `~/.totalsegmentator` ở lần chạy đầu
(cần mạng), hoặc đặt sẵn vào `models/totalseg_weights` + biến môi trường `TOTALSEG_HOME_DIR`.

### Lệnh hay dùng

| Việc | Lệnh |
|---|---|
| Mở giao diện | `python -m tachrang` |
| Pipeline dòng lệnh | `python -m tachrang.core.pipeline --help` |
| Kiểm tra GPU | `python -m tachrang --gpu-probe` (in `1` = có CUDA) |
| Unit test | `python -m unittest tests.test_sua_nhan -v` |
| Build bản portable | `python dong_goi/tao_portable.py` |
| Build bộ cài Setup.exe | `python dong_goi/tao_setup.py` (cần [Inno Setup 6](https://jrsoftware.org/isinfo.php)) |

### Cấu trúc dự án

```
tachrang/            # gói chính
├── __main__.py      #   python -m tachrang (GUI / --pipeline / --gpu-probe)
├── cau_hinh.py      #   đọc config.json, đường dẫn gốc
├── nhat_ky.py       #   ghi log + diễn giải lỗi thân thiện
├── core/            #   pipeline tách răng, ghép chân răng 3Shape, xử lý lưới
└── ui/giao_dien.py  #   giao diện PySide6 + VTK (kiểu 3D Slicer)
dong_goi/            # script đóng gói portable + bộ cài Inno Setup
tests/               # unit test + test giao diện end-to-end
tools/               # tiện ích kiểm tra/chụp ảnh kết quả khi phát triển
```

---

## 4. Riêng tư & lưu ý

- **Repo này chỉ chứa mã nguồn** — không có ảnh bệnh nhân, không có kết quả tách,
  không có model set 3Shape (xem `.gitignore`).
- Toàn bộ xử lý AI chạy cục bộ trên máy người dùng; app không gửi dữ liệu đi đâu.
- Model DentalSegmentator / TotalSegmentator thuộc các dự án gốc với giấy phép riêng
  của họ; phần mềm này chỉ dùng để hỗ trợ chẩn đoán/lập kế hoạch, **không thay thế
  quyết định lâm sàng của bác sĩ**.
