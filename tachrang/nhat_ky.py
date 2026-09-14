# -*- coding: utf-8 -*-
"""nhat_ky.py — Ghi log ra file + đổi lỗi kỹ thuật thành lời giải thích dễ hiểu.

Quy ước với giao diện: khi pipeline gặp lỗi không xử lý được, nó in ra stdout
    [LOI] <một câu tiếng Việt dễ hiểu>
    [LOI-LOG] <đường dẫn file log chứa traceback đầy đủ>
rồi thoát với mã 2. Giao diện đọc 2 dòng này để hiện hộp thoại.
"""

import datetime
import logging
import platform
import sys
import traceback
from pathlib import Path

from . import cau_hinh, __version__

DAU_LOI = "[LOI]"
DAU_LOG = "[LOI-LOG]"


def bat_dau_log(ten: str) -> Path:
    """Tạo logger ghi vào logs/<ten>_YYYY-MM-DD.log (nối thêm). Trả về đường dẫn."""
    d = cau_hinh.thu_muc_logs()
    f = d / f"{ten}_{datetime.date.today():%Y-%m-%d}.log"
    log = logging.getLogger("tachrang")
    if not any(isinstance(h, logging.FileHandler)
               and Path(h.baseFilename) == f for h in log.handlers):
        h = logging.FileHandler(f, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(h)
    log.setLevel(logging.INFO)
    log.info("=== %s v%s | python %s | %s ===", ten, __version__,
             platform.python_version(), platform.platform())
    return f


def log() -> logging.Logger:
    return logging.getLogger("tachrang")


def _co(chuoi: str, *tu) -> bool:
    c = chuoi.lower()
    return any(t in c for t in tu)


def giai_thich(e: BaseException) -> str:
    """Một câu tiếng Việt cho người dùng cuối, kèm gợi ý cách xử lý."""
    s = f"{type(e).__name__}: {e}"
    if isinstance(e, MemoryError) or _co(s, "unable to allocate", "not enough memory",
                                          "paging file", "bad allocation"):
        return ("Máy HẾT RAM khi xử lý ảnh này. Hãy đóng các chương trình khác, "
                "hoặc thử chế độ DentalSegmentator (nhẹ hơn), hoặc dùng máy có RAM ≥16GB.")
    if _co(s, "cuda out of memory", "cublas_status_alloc_failed", "cudnn_status_not_initialized"):
        return ("Card đồ họa HẾT bộ nhớ (VRAM). Hãy đóng phần mềm dùng GPU khác rồi chạy lại, "
                "hoặc chọn Thiết bị = cpu (chậm hơn nhưng luôn chạy được).")
    if _co(s, "cuda error", "no kernel image", "cuda driver version"):
        return ("Lỗi driver/CUDA của card đồ họa. Hãy cập nhật driver NVIDIA, "
                "hoặc chọn Thiết bị = cpu.")
    if isinstance(e, ImportError) or _co(s, "no module named"):
        return (f"Thiếu thư viện Python ({e}). Chạy: pip install -r requirements.txt "
                "(hoặc cài lại chương trình).")
    if _co(s, "checkpoint_final.pth", "plans.json", "dataset.json", "model_dir", "totalseg"
           ) and _co(s, "no such file", "not found", "không tìm thấy", "filenotfound"):
        return ("Thiếu file MODEL AI. Kiểm tra thư mục models/ (hoặc TACHRANG_MODELS), "
                "hoặc nối mạng để chương trình tự tải model lần đầu.")
    if _co(s, "urlopen", "httperror", "urlerror", "connection", "timed out", "ssl", "getaddrinfo"):
        return ("Không tải được model/dữ liệu từ Internet. Kiểm tra kết nối mạng, "
                "hoặc chép sẵn thư mục models/ từ máy khác.")
    if _co(s, "gdcm", "dicom", "itk exception", "unable to determine imageio", "series"):
        return ("Không đọc được ảnh DICOM/CBCT này (định dạng lạ, thiếu file hay ảnh nén "
                "chưa hỗ trợ). Hãy xuất lại từ máy chụp dạng DICOM chuẩn hoặc .nii.gz.")
    if isinstance(e, PermissionError) or _co(s, "permission denied", "access is denied",
                                             "being used by another process"):
        return ("Không ghi được file (thư mục chỉ-đọc hoặc file đang mở ở chương trình khác). "
                "Đóng file/thư mục đó rồi chạy lại, hoặc chọn thư mục kết quả khác.")
    if _co(s, "no space left", "disk full", "không đủ dung lượng"):
        return "Ổ đĩa đầy. Hãy giải phóng dung lượng rồi chạy lại."
    if isinstance(e, KeyboardInterrupt):
        return "Đã dừng theo yêu cầu."
    return f"Lỗi không mong đợi: {s}"


def bao_loi(e: BaseException, noi: str = "") -> str:
    """Ghi traceback đầy đủ vào log, in 2 dòng [LOI]/[LOI-LOG] ra stdout,
    trả về câu giải thích."""
    lg = log()
    lg.error("%s%s", f"{noi}: " if noi else "", "".join(
        traceback.format_exception(type(e), e, e.__traceback__)))
    cau = giai_thich(e)
    duong = ""
    for h in lg.handlers:
        if isinstance(h, logging.FileHandler):
            duong = h.baseFilename
    print(f"\n{DAU_LOI} {cau}")
    if duong:
        print(f"{DAU_LOG} {duong}")
    sys.stdout.flush()
    return cau


def tach_loi_tu_log(text: str):
    """Từ output của pipeline lấy (câu lỗi, đường dẫn log) — dòng [LOI] cuối cùng."""
    cau, duong = "", ""
    for line in text.splitlines():
        t = line.strip()
        if t.startswith(DAU_LOI):
            cau = t[len(DAU_LOI):].strip()
        elif t.startswith(DAU_LOG):
            duong = t[len(DAU_LOG):].strip()
    return cau, duong
