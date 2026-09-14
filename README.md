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
1. Mở app → bấm **Chọn thư mục DICOM** — hoặc **kéo-thả** thẳng thư mục/file vào cửa sổ:
   app tự nhận dạng thư mục DICOM (kể cả thư mục cha nhiều ca — sẽ hỏi chọn ca),
   file dự án `.tachrang`, bản đồ nhãn `.nii.gz`, scan hàm `.stl/.ply/.obj`.
2. Ảnh hiện ngay trên 3 mặt cắt. Bấm **Tách răng** — chế độ `auto` tự chọn GPU/CPU
   và cấu hình phù hợp với máy.
3. Xong, kết quả tự hiển thị trong khung 3D:
   - Từng răng đánh số **FDI** (11–48), xương hàm trên/dưới, ống thần kinh.
   - File STL nằm trong `ket_qua\stl\<tên ca>\` — mở được bằng mọi phần mềm CAD/in 3D.
4. Tab **Sửa nhãn**: lấp lỗ theo ngưỡng, làm mịn, mọc từ hạt, hoàn tác… nếu muốn tinh chỉnh.

### Dự án — mở lại ca cũ chỉ một cú bấm
- Mỗi khi nạp một ca, app tự ghi file dự án `<kết quả>\du_an\<tên ca>.tachrang`
  (file nhỏ kiểu con trỏ, giống project của Blue Sky Plan / RealGUIDE — dữ liệu nặng
  vẫn nằm trong thư mục kết quả).
- Bấm **Gần đây ▾** để mở lại ca đã làm — DICOM + kết quả + scan trở lại nguyên trạng;
  mục nào có bản làm dở/kết quả sẽ được ghi chú ngay trong menu.
- **Mở dự án…** / **Lưu dự án** để mở hoặc lưu file `.tachrang` ở nơi khác (USB, ổ mạng…).
  Nếu thư mục DICOM gốc đã bị xoá, dự án vẫn mở được phần kết quả (CT nền lấy từ
  `staged_inputs`). Bản làm dở **không bao giờ tự nạp** — chỉ nạp khi bấm
  *↻ Khôi phục bản làm dở*.

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

**Model AI** (không nằm trong git — lấy từ bản cài sẵn trong Releases, hoặc tự đặt vào;
nguồn gốc và giấy phép từng model xem mục 4):

```
models/
├── DentalSegmentator/   # nnU-Net 3d_fullres: xương hàm trên/dưới, khối răng, ống TK  (Dot G. et al. 2024)
└── UniversalLab/        # nnU-Net: từng răng + răng sửa (DCBIA-OrthoLab, chế độ tuỳ chọn)
```

Trọng số TotalSegmentator (răng FDI, xoang, sọ–hàm) tự tải về `~/.totalsegmentator` ở lần chạy đầu
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

## 4. AI trong phần mềm — từ đâu, huấn luyện bằng gì, giấy phép ra sao

TachRang **không tự huấn luyện model**. Phần mềm dùng lại các model phân đoạn mã nguồn mở đã được
công bố trên tạp chí khoa học, chạy chúng trên máy người dùng, rồi **tự viết phần hậu xợ lý**
(chia khối răng thành từng răng, đánh số FDI, làm mịn STL, căn scan, ghép 3Shape, giao diện).

### 4.1 Ba model đang dùng

| Model (thư mục) | Ai làm ra | Huấn luyện trên dữ liệu gì | Cho ra gì | TachRang dùng để |
|---|---|---|---|---|
| **DentalSegmentator** (`models/DentalSegmentator`) | G. Dot, L. Gajny (Université Paris Cité / AP-HP / Arts-et-Métiers) + Kitware SAS; tài trợ FFO & Fondation des Gueules Cassées | nnU-Net v2, **470 ca CT+CBCT** đa trung tâm, kiểm định trên 256 ca từ 7 cơ sở | 5 nhãn: xương hàm trên+sọ, xương hàm dưới, khối răng trên, khối răng dưới, ống thần kinh hàm dưới | Xương + khối răng + ống TK (bền nhất với máy chụp lạ, nhiễu kim loại) — **model chính** |
| **TotalSegmentator** task `teeth` và `craniofacial_structures` (tự tải vào `~/.totalsegmentator`) | J. Wasserthal và cộng sự, Bệnh viện Đại học Basel (Thụy Sĩ) | nnU-Net; task `teeth` huấn luyện từ bộ dữ liệu **ToothFairy3** (CBCT, Bolelli et al. CVPR 2025); task sọ–mặt theo bài IJOMS 2025 | `teeth`: 77 nhãn — từng răng **FDI 11–48**, tủy từng răng, xoang hàm trái/phải, ống TK, implant/crown/bridge; `craniofacial_structures`: xương hàm dưới trọn vẹn, sọ, xoang | Hạt giống số FDI để chia khối răng của DentalSegmentator thành từng răng; xoang hàm; xương bổ sung |
| **UniversalLab** (`models/UniversalLab`, tuỳ chọn) | DCBIA-OrthoLab (ĐH Michigan / UNC), extension *Slicer Automated Dental Tools*, module BatchDentalSegmentator | nnU-Net, **513 ca CBCT** gồm cả răng sửa | 55 nhãn: từng răng vĩnh viễn + răng sửa (Universal Numbering), xương hàm, ống TK | Chế độ phụ cho ca có răng sửa; kém bền với CBCT ngoài dải HU chuẩn |

Tất cả đều chạy trên khung **nnU-Net** (Đức, DKFZ) và **PyTorch**. Chế độ mặc định *KẾT HỢP* =
DentalSegmentator (xương/khối răng chuẩn) + TotalSegmentator `teeth` (số FDI) → thuật toán riêng của
TachRang (watershed + gộp “yên ngựa” + đánh số theo bề rộng răng) cho ra từng răng riêng lẻ.

### 4.2 Nguồn tải & giấy phép (đã kiểm tra 09/2026)

| Thành phần | Nguồn tải chính thức | Giấy phép | Ý nghĩa với người dùng |
|---|---|---|---|
| DentalSegmentator — mã extension | https://github.com/gaudot/SlicerDentalSegmentator | **Apache 2.0** (© 2024 Gauthier Dot) | Dùng/sửa/phân phối tự do, kể cả thương mại, phải giữ ghi công |
| DentalSegmentator — trọng số (`Dataset111_453CT_v100.zip` / Zenodo `Dataset112_DentalSegmentator_v100.zip`) | GitHub Releases của repo trên; Zenodo DOI [10.5281/zenodo.10829675](https://doi.org/10.5281/zenodo.10829675) | **CC BY 4.0** (Zenodo) | Dùng tự do kể cả thương mại, **bắt buộc ghi tác giả + trích dẫn bài báo** |
| TotalSegmentator — mã (pip `TotalSegmentator`) | https://github.com/wasserth/TotalSegmentator | **Apache 2.0** | Tự do |
| TotalSegmentator — trọng số task `teeth`, `craniofacial_structures` | Tự tải từ GitHub Releases của repo trên | Thuộc nhóm tác giả ghi rõ **“Openly available for any usage (Apache-2.0)”** | Tự do. *Lưu ý:* một số task khác của TotalSegmentator (heartchambers_highres, appendicular_bones, tissue_types, face, coronary…) **cần license riêng** — TachRang **không** dùng các task đó |
| UniversalLab — trọng số (`UNIVERSALLAB_MODEL`) | https://github.com/DCBIA-OrthoLab/SlicerAutomatedDentalTools/releases | Repo **Apache 2.0**; trọng số phát hành cùng repo, không có file license riêng → coi theo Apache 2.0, nên hỏi tác giả nếu dùng thương mại | Tự do (nghiên cứu/lâm sàng nội bộ) |
| nnU-Net v2 (pip `nnunetv2`) | https://github.com/MIC-DKFZ/nnUNet | Apache 2.0 | Tự do |

Chỉ có **hai** điểm trên máy người dùng cần Internet: tải trọng số lần đầu (nếu chưa có sẵn) và
kiểm tra phiên bản. **Thống kê sự dụng ẩn danh** mà TotalSegmentator bật mặc định (gửi task,
thiết bị, thời gian chạy về `backend.totalsegmentator.com`) được TachRang chặn bằng 3 lớp
(`tachrang.core.pipeline.tat_thong_ke_totalseg`):
1. ghi `send_usage_stats: false` vào `config.json` của TotalSegmentator (cách chính thức của tác giả) —
   bản portable/Setup đã được tạo sẵn với cờ này tắt;
2. thay hàm `send_usage_stats` trong thư viện bằng hàm rỗng trước mọi lần chạy → dù config bị bật lại cũng
   không tạo request nào (đã test: 0 request khi giả lập cờ bật);
3. không dùng task cần license (không có bước xác thực license online).

Không có dữ liệu ảnh hay kết quả nào rời khỏi máy. Muốn chặn triệt để cả việc tải model:
chép sẵn `models/` từ bản cài đầy đủ rồi ngắt mạng — app vẫn chạy bình thường.

### 4.3 Thư viện nền (kèm trong bản cài)

| Thư viện | Phiên bản đã kiểm | Giấy phép |
|---|---|---|
| PyTorch (+ CUDA 12.6 runtime) | 2.14 | BSD-3-Clause; thư viện CUDA/cuDNN theo **NVIDIA EULA** (được phép phân phối kèm ứng dụng) |
| nnunetv2, batchgenerators, dynamic_network_architectures | 2.8 / 0.25 / 0.4 | Apache 2.0 |
| TotalSegmentator | 2.18 | Apache 2.0 |
| SimpleITK | 2.5 | Apache 2.0 |
| VTK | 9.3 | BSD-3-Clause |
| PySide6 / shiboken6 (Qt 6) | 6.11 | **LGPL-3.0** (hoặc GPL/thương mại Qt) — TachRang liên kết động, không sửa Qt, người dùng thay được file DLL → thoả LGPL |
| Open3D | 0.19 | MIT |
| NumPy, SciPy, scikit-image, psutil | 2.4 / 1.17 / 0.26 / 7.2 | BSD-3-Clause |
| nibabel | 5.4 | MIT |
| Inno Setup (chỉ dùng khi đóng gói) | 6 | Inno Setup License (miễn phí, kể cả thương mại) |

### 4.4 Tài liệu tham khảo — hãy trích dẫn khi công bố kết quả dùng TachRang

1. **Dot G.**, Chaurasia A., Dubois G., Savoldelli C., Haghighat S., Azimian S., Taramsari A.R., Sivaramakrishnan G., Issa J., Dubey A., Schouman T., Gajny L. *DentalSegmentator: Robust open source deep learning-based CT and CBCT image segmentation.* **Journal of Dentistry** 147 (2024) 105130. doi:[10.1016/j.jdent.2024.105130](https://doi.org/10.1016/j.jdent.2024.105130)
2. **Wasserthal J.**, Breit H.-C., Meyer M.T., Pradella M., Hinck D., Sauter A.W., Heye T., Boll D., Cyriac J., Yang S., Bach M., Segeroth M. *TotalSegmentator: Robust Segmentation of 104 Anatomic Structures in CT Images.* **Radiology: Artificial Intelligence** 5(5) (2023) e230024. doi:[10.1148/ryai.230024](https://doi.org/10.1148/ryai.230024)
3. **Bolelli F.** et al. *Segmenting Maxillofacial Structures in CBCT Volumes* (bộ dữ liệu ToothFairy3 — nền của task `teeth`). **CVPR 2025**. [Link](https://openaccess.thecvf.com/content/CVPR2025/html/Bolelli_Segmenting_Maxillofacial_Structures_in_CBCT_Volumes_CVPR_2025_paper.html)
4. Bài báo task `craniofacial_structures` của TotalSegmentator: **Int. J. Oral Maxillofac. Surg.** (2025). [Link](https://www.ijoms.com/article/S0901-5027(25)01499-7/fulltext)
5. **Isensee F.**, Jaeger P.F., Kohl S.A.A., Petersen J., Maier-Hein K.H. *nnU-Net: a self-configuring method for deep learning-based biomedical image segmentation.* **Nature Methods** 18 (2021) 203–211. doi:[10.1038/s41592-020-01008-z](https://doi.org/10.1038/s41592-020-01008-z)
6. DCBIA-OrthoLab. *Slicer Automated Dental Tools* (module BatchDentalSegmentator, model UniversalLabDentalSegmentator). https://github.com/DCBIA-OrthoLab/SlicerAutomatedDentalTools — tài trợ NIDCR R01DE024450.
7. Zhou Q.-Y., Park J., Koltun V. *Open3D: A Modern Library for 3D Data Processing.* arXiv:1801.09847 (2018) — dùng cho căn scan (FPFH/RANSAC/ICP).

Mẫu trích dẫn phần mềm này: *TachRang — Tách răng tự động từ CBCT (phiên bản x.y.z), https://github.com/tjmyou123/tach-rang-cbct, dựa trên DentalSegmentator [1], TotalSegmentator [2,3,4] và nnU-Net [5].*

### 4.5 Kiểm tra bản quyền — trạng thái tuân thủ

| Yêu cầu | Trạng thái |
|---|---|
| Ghi công tác giả model (Apache 2.0 §4, CC BY 4.0 §3) | ✅ Mục 4.1–4.4 của README này; tên model giữ nguyên trong `models/` và log |
| Không dùng task TotalSegmentator cần license thương mại | ✅ Chỉ gọi `teeth`, `craniofacial_structures` (nhóm Apache 2.0) |
| Không sửa đổi trọng số model | ✅ Dùng nguyên bản; mọi cải tiến nằm ở hậu xợ lý trong `tachrang/core` |
| Qt/PySide6 theo LGPL: liên kết động, DLL thay được, không xáo trộn | ✅ Bản portable/Setup giữ nguyên các file `Qt6*.dll`, `PySide6/` |
| CUDA runtime phân phối theo NVIDIA EULA | ✅ Chỉ kèm các file redistributable trong wheel `nvidia-*` |
| Không gởi dữ liệu bệnh nhân ra ngoài | ✅ Xợ lý cục bộ; thống kê TotalSegmentator đã tắt tự động |
| Nhãn hiệu bên thứ ba | ⚠️ *3Shape*, *OrthoAnalyzer* là nhãn hiệu của 3Shape A/S; TachRang **không liên kết, không được 3Shape bảo trợ** — chỉ đọc/ghi file dữ liệu trên máy người dùng theo yêu cầu của chính người dùng đó (luôn sao lưu trước). Kiểm tra điều khoản EULA 3Shape của cơ sở bạn trước khi dùng trên dữ liệu lâm sàng |
| Giấy phép của chính TachRang | ✅ **Apache License 2.0** — file [LICENSE](LICENSE); ghi công bên thứ ba trong [NOTICE](NOTICE). Cả hai được chép vào bản portable và bộ cài (Setup hiện trang giấy phép khi cài) |
| Thiết bị y tế | ⚠️ Chưa đăng ký/chứng nhận (CE/FDA/Bộ Y tế). Chỉ dùng hỗ trợ lập kế hoạch/nghiên cứu; bác sĩ chịu trách nhiệm kiểm tra kết quả |

---

## 5. Riêng tư & lưu ý

- **Repo này chỉ chứa mã nguồn** — không có ảnh bệnh nhân, không có kết quả tách,
  không có model set 3Shape (xem `.gitignore`).
- Toàn bộ xợ lý AI chạy cục bộ trên máy người dùng; app không gởi dữ liệu đi đâu
  (kết nối mạng duy nhất: tải trọng số model lần đầu nếu chưa có sẵn).
- Model DentalSegmentator / TotalSegmentator / UniversalLab thuộc các nhóm tác giả gốc
  với giấy phép nêu ở mục 4.2; phần mềm này chỉ dùng để hỗ trợ chẩn đoán/lập kế hoạch,
  **không thay thế quyết định lâm sàng của bác sĩ**.

## 6. Giấy phép

TachRang được phát hành theo **Apache License 2.0** — xem [LICENSE](LICENSE). Bạn được dùng,
sửa, phân phối (kể cả thương mại) với điều kiện giữ nguyên file LICENSE + [NOTICE](NOTICE) và ghi
rõ những file bạn đã sửa. File NOTICE liệt kê đầy đủ ghi công cho DentalSegmentator (CC BY 4.0),
TotalSegmentator, nnU-Net, Qt/PySide6 (LGPL) và các thư viện khác.
