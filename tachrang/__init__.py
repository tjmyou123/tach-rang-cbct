"""tachrang — Tách răng CBCT: AI phân đoạn → từng răng FDI/xương/xoang → STL.

Cấu trúc:
  tachrang.core.pipeline  : quy trình xử lý (CLI: python -m tachrang.core.pipeline)
  tachrang.core.sua_nhan  : thuật toán sửa nhãn (ngưỡng, làm mịn, mọc từ hạt)
  tachrang.ui             : giao diện PySide6 + VTK (python -m tachrang)
  tachrang.cau_hinh       : đường dẫn/cấu hình (không đường dẫn cứng)
  tachrang.nhat_ky        : ghi log ra file + giải thích lỗi thân thiện
"""

__version__ = "0.9.0"
