# -*- coding: utf-8 -*-
"""python -m tachrang            → mở giao diện
python -m tachrang --pipeline … → chạy pipeline dòng lệnh (giống tachrang.core.pipeline)
python -m tachrang --gpu-probe  → in 1/0 (có GPU CUDA hay không) rồi thoát
"""
import multiprocessing
import os
import sys
from pathlib import Path


def _chuan_bi_moi_truong():
    """Bản đóng gói: tự trỏ TOTALSEG_HOME_DIR vào kho trọng số đi kèm,
    để shortcut/installer chạy thẳng pythonw -m tachrang không cần file .bat."""
    if not os.environ.get("TOTALSEG_HOME_DIR"):
        kho = Path(__file__).resolve().parent.parent / "models" / "totalseg_weights"
        if kho.is_dir():
            os.environ["TOTALSEG_HOME_DIR"] = str(kho)


def main():
    multiprocessing.freeze_support()   # bắt buộc khi đóng gói exe: nnU-Net/torch sinh tiến trình con
    _chuan_bi_moi_truong()
    if len(sys.argv) > 1 and sys.argv[1] == "--pipeline":
        del sys.argv[1]
        from .core.pipeline import main as pl_main
        pl_main()
    elif len(sys.argv) > 1 and sys.argv[1] == "--gpu-probe":
        try:
            import torch
            print(int(torch.cuda.is_available()))
        except Exception:
            print(0)
    elif len(sys.argv) >= 3 and sys.argv[1] == "--preview":
        from pathlib import Path
        from .ui.giao_dien import show_preview
        show_preview(Path(sys.argv[2]))
    else:
        from .ui.giao_dien import run_gui
        run_gui()


if __name__ == "__main__":
    main()
