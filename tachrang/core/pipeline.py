#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tachrang.core.pipeline — Tách từng răng từ CBCT thành file STL riêng, hoàn toàn tự động.

(File cũ: tach_rang_pipeline.py ở gốc dự án giờ chỉ là lịch gọi sang module này.)

Pipeline:
  1. Đọc mọi ảnh CBCT trong thư mục input (.nii/.nii.gz/.nrrd/.gipl/.mha hoặc thư mục DICOM)
  2. Chạy AI phân đoạn nnU-Net "UniversalLabDentalsegmentator" (mỗi răng 1 nhãn riêng,
     model tải tự động từ GitHub release của SlicerAutomatedDentalTools lần chạy đầu)
  3. Tách mỗi nhãn răng thành 1 mesh 3D -> làm mượt -> xuất STL riêng cho từng răng

Cách dùng (tại thư mục gốc dự án; hoặc gọi qua lịch `python tach_rang_pipeline.py`):
  # Chạy full tự động (phân đoạn + tách STL từng răng):
  python -m tachrang.core.pipeline -i "D:/data/cbct" -o "D:/data/output" --model combo

  # Tách răng (FDI) + XOANG HÀM trái/phải (model TotalSegmentator task "teeth"):
  python tach_rang_pipeline.py -i ... -o ... --model totalseg
  #   thêm --include-pulp để xuất tủy từng răng,
  #   thêm --include-bones để xuất xương hàm/ống thần kinh/hầu họng/implant...

  # Nếu đã có sẵn file phân đoạn (vd: output của BatchDentalSegmentator trong Slicer),
  # chỉ cần tách STL:
  python tach_rang_pipeline.py -i "D:/data/segmentations" -o "D:/data/output" --seg-only

  # Xuất thêm cả xương hàm (Mandible/Maxilla/Mandibular canal):
  python tach_rang_pipeline.py -i ... -o ... --include-bones

Cài đặt thư viện:
  # Chỉ tách STL (--seg-only):
  pip install SimpleITK vtk numpy
  # Full pipeline (thêm AI, cần GPU NVIDIA):
  pip install torch --index-url https://download.pytorch.org/whl/cu126
  pip install nnunetv2
  # Model totalseg (tách thêm xoang hàm):
  pip install TotalSegmentator

Ghi chú:
  - Tọa độ STL xuất ra theo hệ LPS (chuẩn ITK/DICOM). Mở lại trong 3D Slicer sẽ khớp
    đúng vị trí với ảnh CBCT gốc.
  - Chạy lại script sẽ tự bỏ qua các ca đã phân đoạn xong (resume được).
"""

import argparse
import csv
import json
import os
import re
import shutil
import sys
import tempfile
import urllib.request
from pathlib import Path

import numpy as np
import SimpleITK as sitk
import vtk
from vtk.util.numpy_support import numpy_to_vtk

if __package__ in (None, ""):  # chạy trực tiếp file .py -> thêm gốc dự án vào sys.path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tachrang import cau_hinh, nhat_ky  # noqa: E402

# ── Nhãn của model UniversalLabDentalsegmentator ──────────────────────────────
# (khớp SegmentationWidget._get_active_label_map trong SlicerAutomatedDentalTools)
LABEL_NAMES = {
    1: "Upper-right third molar", 2: "Upper-right second molar", 3: "Upper-right first molar",
    4: "Upper-right second premolar", 5: "Upper-right first premolar", 6: "Upper-right canine",
    7: "Upper-right lateral incisor", 8: "Upper-right central incisor", 9: "Upper-left central incisor",
    10: "Upper-left lateral incisor", 11: "Upper-left canine", 12: "Upper-left first premolar",
    13: "Upper-left second premolar", 14: "Upper-left first molar", 15: "Upper-left second molar",
    16: "Upper-left third molar", 17: "Lower-left third molar", 18: "Lower-left second molar",
    19: "Lower-left first molar", 20: "Lower-left second premolar", 21: "Lower-left first premolar",
    22: "Lower-left canine", 23: "Lower-left lateral incisor", 24: "Lower-left central incisor",
    25: "Lower-right central incisor", 26: "Lower-right lateral incisor", 27: "Lower-right canine",
    28: "Lower-right first premolar", 29: "Lower-right second premolar", 30: "Lower-right first molar",
    31: "Lower-right second molar", 32: "Lower-right third molar",
    33: "Upper-right second molar (baby)", 34: "Upper-right first molar (baby)",
    35: "Upper-right canine (baby)", 36: "Upper-right lateral incisor (baby)",
    37: "Upper-right central incisor (baby)", 38: "Upper-left central incisor (baby)",
    39: "Upper-left lateral incisor (baby)", 40: "Upper-left canine (baby)",
    41: "Upper-left first molar (baby)", 42: "Upper-left second molar (baby)",
    43: "Lower-left second molar (baby)", 44: "Lower-left first molar (baby)",
    45: "Lower-left canine (baby)", 46: "Lower-left lateral incisor (baby)",
    47: "Lower-left central incisor (baby)", 48: "Lower-right central incisor (baby)",
    49: "Lower-right lateral incisor (baby)", 50: "Lower-right canine (baby)",
    51: "Lower-right first molar (baby)", 52: "Lower-right second molar (baby)",
    53: "Mandible", 54: "Maxilla", 55: "Mandibular canal",
}
BABY_LETTERS = "ABCDEFGHIJKLMNOPQRST"  # nhãn 33..52 = răng sữa A..T (Universal Numbering)
BONE_LABELS = {53, 54, 55}

MODEL_RELEASE = ("https://github.com/DCBIA-OrthoLab/SlicerAutomatedDentalTools/"
                 "releases/download/UNIVERSALLAB_MODEL/")
MODEL_FILES = {
    "dataset.json": MODEL_RELEASE + "dataset.json",
    "plans.json": MODEL_RELEASE + "plans.json",
    os.path.join("fold_0", "checkpoint_final.pth"): MODEL_RELEASE + "checkpoint_final.pth",
}

# Model DentalSegmentator (Dot G. et al., Journal of Dentistry 2024) — nnU-Net
# huấn luyện trên 453 ca CT+CBCT đa trung tâm -> rất bền vững với máy chụp lạ.
DENTSEG_ZIP_URL = ("https://github.com/gaudot/SlicerDentalSegmentator/releases/"
                   "download/v1.0.0-alpha/Dataset111_453CT_v100.zip")
DENTSEG_LABELS = {
    1: "Upper-Skull-Maxilla", 2: "Mandible", 3: "Upper-Teeth",
    4: "Lower-Teeth", 5: "Mandibular-canal",
}

# Model TotalSegmentator task "teeth" (ToothFairy3): mỗi cấu trúc 1 file mask nhị phân.
# Răng đánh số FDI 11-48 (đuôi _fdiXX), tủy răng _pulp_fdi1XX, xoang hàm *_maxillary_sinus.
TEETH_FDI_RE = re.compile(r"_fdi(\d{2})$")

IMG_EXTS = (".nii.gz", ".nii", ".nrrd", ".nhdr", ".gipl.gz", ".gipl", ".mha", ".mhd")


def case_stem(path: Path) -> str:
    """Tên ca bệnh: bỏ đuôi file (xử lý cả đuôi kép .nii.gz)."""
    name = path.name
    for ext in IMG_EXTS:
        if name.lower().endswith(ext):
            return name[: -len(ext)]
    return path.stem


def sanitize(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-")


def uns_code(label: int) -> str:
    """Mã răng theo Universal Numbering System: 01-32 (vĩnh viễn), A-T (răng sữa)."""
    if 1 <= label <= 32:
        return f"{label:02d}"
    if 33 <= label <= 52:
        return BABY_LETTERS[label - 33]
    return f"L{label}"


# ── Bước 1: gom & chuẩn hoá input ─────────────────────────────────────────────

def read_dicom_series(folder: Path):
    reader = sitk.ImageSeriesReader()
    try:
        series_ids = reader.GetGDCMSeriesIDs(str(folder))
    except Exception:
        return None
    best, best_n = None, 0
    for sid in series_ids:
        files = reader.GetGDCMSeriesFileNames(str(folder), sid)
        if len(files) > best_n:
            best, best_n = files, len(files)
    if not best or best_n < 10:
        return None
    reader.SetFileNames(best)
    return reader.Execute()


def read_dicom_series_deep(folder: Path):
    """Đọc chuỗi DICOM trong folder; nếu không có, tìm tiếp ở các thư mục con
    (nhiều máy CBCT xuất ảnh vào thư mục lồng vài lớp)."""
    img = read_dicom_series(folder)
    if img is not None:
        return img
    subdirs = sorted((p for p in folder.rglob("*") if p.is_dir()),
                     key=lambda p: -sum(1 for f in p.iterdir() if f.is_file()))
    for d in subdirs:
        img = read_dicom_series(d)
        if img is not None:
            return img
    return None


def stage_inputs(input_dir: Path, staging_dir: Path):
    """Chuyển mọi input về .nii.gz trong staging_dir. Trả về [(case, path)]."""
    staging_dir.mkdir(parents=True, exist_ok=True)
    pairs = []

    files = sorted(p for p in input_dir.iterdir()
                   if p.is_file() and p.name.lower().endswith(IMG_EXTS))
    for f in files:
        case = sanitize(case_stem(f))
        staged = staging_dir / f"{case}.nii.gz"
        if not staged.exists():
            print(f"  [stage] {f.name} -> {staged.name}")
            sitk.WriteImage(sitk.ReadImage(str(f)), str(staged))
        pairs.append((case, staged))

    # Thư mục con: thử đọc như chuỗi DICOM (tìm cả thư mục lồng sâu)
    for d in sorted(p for p in input_dir.iterdir() if p.is_dir()):
        case = sanitize(d.name)
        staged = staging_dir / f"{case}.nii.gz"
        if staged.exists():
            pairs.append((case, staged))
            continue
        img = read_dicom_series_deep(d)
        if img is not None:
            print(f"  [stage] DICOM {d.name}/ -> {staged.name}")
            sitk.WriteImage(img, str(staged))
            pairs.append((case, staged))

    # Chính thư mục input là 1 series DICOM?
    if not pairs:
        img = read_dicom_series(input_dir)
        if img is not None:
            case = sanitize(input_dir.name)
            staged = staging_dir / f"{case}.nii.gz"
            print(f"  [stage] DICOM {input_dir.name}/ -> {staged.name}")
            sitk.WriteImage(img, str(staged))
            pairs.append((case, staged))

    return pairs


def stage_single_case(input_dir: Path, staging_dir: Path):
    """Coi input_dir là dữ liệu của MỘT bệnh nhân duy nhất (tên ca = tên thư mục)."""
    staging_dir.mkdir(parents=True, exist_ok=True)
    case = sanitize(input_dir.name)
    staged = staging_dir / f"{case}.nii.gz"
    if staged.exists():
        return [(case, staged)]
    files = sorted(p for p in input_dir.iterdir()
                   if p.is_file() and p.name.lower().endswith(IMG_EXTS))
    if files:
        print(f"  [stage] {files[0].name} -> {staged.name}")
        sitk.WriteImage(sitk.ReadImage(str(files[0])), str(staged))
        return [(case, staged)]
    img = read_dicom_series_deep(input_dir)
    if img is None:
        return []
    print(f"  [stage] DICOM {input_dir.name}/ -> {staged.name}")
    sitk.WriteImage(img, str(staged))
    return [(case, staged)]


# ── Bước 2: phân đoạn nnU-Net ────────────────────────────────────────────────

def total_ram_gb() -> float:
    """Tổng RAM vật lý của máy (GB)."""
    try:
        if os.name == "nt":
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_uint64), ("ullAvailPhys", ctypes.c_uint64),
                    ("ullTotalPageFile", ctypes.c_uint64), ("ullAvailPageFile", ctypes.c_uint64),
                    ("ullTotalVirtual", ctypes.c_uint64), ("ullAvailVirtual", ctypes.c_uint64),
                    ("ullAvailExtendedVirtual", ctypes.c_uint64)]

            st = MEMORYSTATUSEX()
            st.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
            return st.ullTotalPhys / 2**30
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2**30
    except Exception:
        return 16.0


def auto_config():
    """Tự đánh giá phần cứng -> (device, tổng hợp trên GPU?, mô tả).

    Quy tắc:
    - Có GPU CUDA -> AI chạy GPU; không có -> CPU.
    - VRAM >= 12GB -> cho GPU ôm luôn phần tổng hợp (nhanh hơn);
      VRAM nhỏ -> tổng hợp trên RAM để tránh tràn bộ nhớ.
    - RAM < 16GB -> cảnh báo ảnh lớn có thể chậm.
    """
    import torch

    ram = total_ram_gb()
    if torch.cuda.is_available():
        props = torch.cuda.get_device_properties(0)
        vram = props.total_memory / 2**30
        on_dev = vram >= 12
        report = (f"GPU {props.name} (VRAM {vram:.0f}GB) + RAM {ram:.0f}GB "
                  f"-> AI trên GPU, tổng hợp trên {'GPU' if on_dev else 'RAM'}")
        if ram < 16:
            report += " | RAM hơi thấp, ảnh lớn có thể chậm"
        return "cuda", on_dev, report
    return "cpu", False, f"Không có GPU CUDA, RAM {ram:.0f}GB -> chạy toàn bộ trên CPU (chậm)"


def download_model(model_dir: Path):
    for rel, url in MODEL_FILES.items():
        dst = model_dir / rel
        if dst.exists() and dst.stat().st_size > 0:
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        print(f"  [model] Đang tải {rel} ...")

        def hook(n, bs, total):
            if total > 0:
                pct = min(100, n * bs * 100 // total)
                sys.stdout.write(f"\r          {pct}% ({n * bs // 2**20} MB)")
                sys.stdout.flush()

        tmp = dst.with_suffix(dst.suffix + ".part")
        urllib.request.urlretrieve(url, tmp, reporthook=hook)
        print()
        tmp.replace(dst)
    print("  [model] Model sẵn sàng:", model_dir)


def download_model_dentseg(model_dir: Path):
    """Tải model DentalSegmentator (zip 219MB trên GitHub) nếu chưa có."""
    need = [model_dir / "dataset.json", model_dir / "plans.json",
            model_dir / "fold_0" / "checkpoint_final.pth"]
    if all(p.is_file() and p.stat().st_size > 0 for p in need):
        print("  [model] Model sẵn sàng:", model_dir)
        return
    import zipfile
    model_dir.parent.mkdir(parents=True, exist_ok=True)
    tmp_zip = model_dir.parent / "dentseg_download.zip"
    print("  [model] Đang tải DentalSegmentator (219MB) ...")
    urllib.request.urlretrieve(DENTSEG_ZIP_URL, tmp_zip)
    tmp_dir = model_dir.parent / "dentseg_tmp"
    with zipfile.ZipFile(tmp_zip) as z:
        z.extractall(tmp_dir)
    src = next(tmp_dir.rglob("nnUNetTrainer__nnUNetPlans__3d_fullres"))
    shutil.move(str(src), str(model_dir))
    shutil.rmtree(tmp_dir, ignore_errors=True)
    tmp_zip.unlink(missing_ok=True)
    print("  [model] Model sẵn sàng:", model_dir)


def run_inference(pairs, seg_dir: Path, model_dir: Path, device_str: str):
    try:
        import torch
        from nnunetv2.inference.predict_from_raw_data import nnUNetPredictor
    except ImportError as e:
        sys.exit(
            f"Thiếu thư viện cho bước AI ({e}).\n"
            "Cài đặt:\n"
            "  pip install torch --index-url https://download.pytorch.org/whl/cu126\n"
            "  pip install nnunetv2\n"
            "Hoặc nếu đã có file phân đoạn sẵn, chạy lại với --seg-only."
        )

    # nnUNet đòi các biến môi trường này tồn tại dù không dùng tới
    dummy = Path(tempfile.gettempdir()) / "nnunet_dummy"
    dummy.mkdir(exist_ok=True)
    for var in ("nnUNet_raw", "nnUNet_preprocessed", "nnUNet_results"):
        os.environ.setdefault(var, str(dummy))

    on_device = False  # phần tổng hợp mặc định nằm trên RAM (an toàn)
    if device_str == "auto":
        device_str, on_device, report = auto_config()
        print("  [auto]", report)
    elif device_str == "cuda" and not torch.cuda.is_available():
        print("  [warn] CUDA không khả dụng, chuyển sang CPU (sẽ chậm).")
        device_str = "cpu"
    device = torch.device(device_str)
    print(f"  [nnUNet] device = {device}")

    # perform_everything_on_device: GPU ôm cả phần tổng hợp chỉ khi VRAM đủ lớn
    # (auto quyết định); nếu không, GPU chỉ chạy mạng AI để tránh tràn VRAM.
    common = dict(tile_step_size=0.5, use_gaussian=True, use_mirroring=True,
                  device=device, verbose=False, verbose_preprocessing=False,
                  allow_tqdm=True)
    try:
        predictor = nnUNetPredictor(perform_everything_on_device=on_device, **common)
    except TypeError:  # nnunetv2 cũ dùng tên tham số khác
        predictor = nnUNetPredictor(perform_everything_on_gpu=on_device, **common)

    predictor.initialize_from_trained_model_folder(
        str(model_dir), use_folds=(0,), checkpoint_name="checkpoint_final.pth")

    seg_dir.mkdir(parents=True, exist_ok=True)
    ins = [[str(p)] for _, p in pairs]
    outs = [str(seg_dir / case) for case, _ in pairs]  # nnUNet tự thêm đuôi file
    if hasattr(predictor, "predict_from_files_sequential"):
        # Chạy tuần tự trong 1 tiến trình: không sao chép dữ liệu lớn qua
        # pipe giữa các tiến trình -> tiết kiệm ~50% RAM với ảnh toàn sọ.
        predictor.predict_from_files_sequential(
            ins, outs, save_probabilities=False, overwrite=False,
            folder_with_segs_from_prev_stage=None)
    else:
        predictor.predict_from_files(
            ins, outs, save_probabilities=False, overwrite=False,
            num_processes_preprocessing=1, num_processes_segmentation_export=1,
            folder_with_segs_from_prev_stage=None, num_parts=1, part_id=0)

    seg_paths = []
    for case, _ in pairs:
        found = sorted(seg_dir.glob(case + ".*"))
        if found:
            seg_paths.append((case, found[0]))
        else:
            print(f"  [warn] Không thấy kết quả phân đoạn cho {case}")
    return seg_paths


# ── Bước 3: tách từng nhãn thành STL ─────────────────────────────────────────

def physical_matrix(img: sitk.Image) -> vtk.vtkMatrix4x4:
    """Ma trận index -> toạ độ vật lý LPS (gồm spacing + direction + origin)."""
    d = np.asarray(img.GetDirection(), dtype=float).reshape(3, 3)
    s = np.diag(img.GetSpacing())
    m = np.eye(4)
    m[:3, :3] = d @ s
    m[:3, 3] = img.GetOrigin()
    vm = vtk.vtkMatrix4x4()
    for i in range(4):
        for j in range(4):
            vm.SetElement(i, j, m[i, j])
    return vm


def voxel_sizes_mm(matrix: vtk.vtkMatrix4x4):
    """Kích thước voxel (mm) theo 3 trục, lấy từ ma trận vật lý."""
    return [float(np.linalg.norm([matrix.GetElement(r, c) for r in range(3)]))
            for c in range(3)]


def mask_to_polydata(mask_zyx: np.ndarray, offset_xyz, matrix: vtk.vtkMatrix4x4,
                     smooth_iterations: int, passband: float, decimate: float,
                     gaussian_mm: float = 0.6):
    """Dựng bề mặt (vtkPolyData, toạ độ vật lý) từ mask nhị phân đã crop."""
    vimg = vtk.vtkImageData()
    zdim, ydim, xdim = mask_zyx.shape
    vimg.SetDimensions(xdim, ydim, zdim)
    vimg.SetSpacing(1.0, 1.0, 1.0)
    vimg.SetOrigin(*offset_xyz)  # toạ độ index toàn cục
    scaled = (np.ascontiguousarray(mask_zyx, dtype=np.uint8) * 100)
    varr = numpy_to_vtk(scaled.ravel(), deep=True)
    vimg.GetPointData().SetScalars(varr)

    contour = vtk.vtkFlyingEdges3D()
    if gaussian_mm > 0:
        vox = voxel_sizes_mm(matrix)
        stds = [min(gaussian_mm / max(v, 1e-6), 3.0) for v in vox]
        cast = vtk.vtkImageCast()
        cast.SetInputData(vimg)
        cast.SetOutputScalarTypeToFloat()
        gauss = vtk.vtkImageGaussianSmooth()
        gauss.SetInputConnection(cast.GetOutputPort())
        gauss.SetStandardDeviations(stds[0], stds[1], stds[2])
        gauss.SetRadiusFactors(3.0, 3.0, 3.0)
        contour.SetInputConnection(gauss.GetOutputPort())
    else:
        contour.SetInputData(vimg)
    contour.SetValue(0, 50.0)
    contour.ComputeNormalsOff()
    contour.ComputeScalarsOff()

    transform = vtk.vtkTransform()
    transform.SetMatrix(matrix)
    to_phys = vtk.vtkTransformPolyDataFilter()
    to_phys.SetInputConnection(contour.GetOutputPort())
    to_phys.SetTransform(transform)

    last = to_phys
    if smooth_iterations > 0:
        smooth = vtk.vtkWindowedSincPolyDataFilter()
        smooth.SetInputConnection(last.GetOutputPort())
        smooth.SetNumberOfIterations(smooth_iterations)
        smooth.SetPassBand(passband)
        smooth.BoundarySmoothingOn()
        smooth.FeatureEdgeSmoothingOff()
        smooth.NonManifoldSmoothingOn()
        smooth.NormalizeCoordinatesOn()
        last = smooth

    if 0.0 < decimate < 1.0:
        deci = vtk.vtkQuadricDecimation()
        deci.SetInputConnection(last.GetOutputPort())
        deci.SetTargetReduction(decimate)
        last = deci

    normals = vtk.vtkPolyDataNormals()
    normals.SetInputConnection(last.GetOutputPort())
    normals.SplittingOff()
    normals.ConsistencyOn()
    normals.AutoOrientNormalsOn()
    normals.Update()
    return normals.GetOutput()


def mask_to_stl(mask_zyx: np.ndarray, offset_xyz, matrix: vtk.vtkMatrix4x4,
                out_path: Path, smooth_iterations: int, passband: float,
                decimate: float, gaussian_mm: float = 0.6):
    """Dựng mesh từ mask nhị phân (đã crop), làm mượt và ghi STL. Trả về (số tam giác, thể tích mm3).

    gaussian_mm > 0: làm mịn Gaussian trên ảnh TRƯỚC khi dựng bề mặt (như
    3D Slicer) — khử “bậc thang” voxel mà vẫn giữ đúng biên (iso 50%).
    """
    poly = mask_to_polydata(mask_zyx, offset_xyz, matrix, smooth_iterations,
                            passband, decimate, gaussian_mm)
    n_tri = poly.GetNumberOfPolys()
    if n_tri == 0:
        return 0, 0.0

    mass = vtk.vtkMassProperties()
    mass.SetInputData(poly)
    volume = float(mass.GetVolume())

    writer = vtk.vtkSTLWriter()
    writer.SetFileName(str(out_path))
    writer.SetFileTypeToBinary()
    writer.SetInputData(poly)
    writer.Write()
    return n_tri, volume


def export_labeled_mask(mask_zyx: np.ndarray, matrix: vtk.vtkMatrix4x4,
                        out_path: Path, min_voxels: int, smooth_iterations: int,
                        passband: float, decimate: float, gaussian_mm: float = 0.6):
    """Crop bbox quanh mask nhị phân, dựng mesh và ghi STL. None nếu quá nhỏ/rỗng."""
    coords = np.argwhere(mask_zyx)
    if coords.shape[0] < min_voxels:
        return None
    zmin, ymin, xmin = coords.min(axis=0)
    zmax, ymax, xmax = coords.max(axis=0)
    # viền đệm đủ rộng cho đuôi Gaussian (3*std) để bề mặt không bị cắt
    pad = 1
    if gaussian_mm > 0:
        vox_min = min(voxel_sizes_mm(matrix))
        pad = 1 + int(np.ceil(3.0 * min(gaussian_mm / max(vox_min, 1e-6), 3.0)))
    crop = np.pad(mask_zyx[zmin:zmax + 1, ymin:ymax + 1, xmin:xmax + 1], pad)
    offset = (float(xmin) - pad, float(ymin) - pad, float(zmin) - pad)
    n_tri, volume = mask_to_stl(crop, offset, matrix, out_path,
                                smooth_iterations, passband, decimate, gaussian_mm)
    if n_tri == 0:
        return None
    return n_tri, volume


def split_case(case: str, seg_path: Path, stl_root: Path, include_bones: bool,
               min_voxels: int, smooth_iterations: int, passband: float,
               decimate: float, manifest_rows: list):
    img = sitk.ReadImage(str(seg_path))
    if img.GetDimension() == 4:  # ví dụ .seg.nrrd nhiều layer
        if img.GetSize()[3] == 1:
            img = img[:, :, :, 0]
        else:
            print(f"  [skip] {seg_path.name}: labelmap 4D nhiều layer, hãy xuất dạng .nii.gz")
            return 0
    arr = sitk.GetArrayViewFromImage(img)  # (z, y, x)
    matrix = physical_matrix(img)

    labels = [int(v) for v in np.unique(arr) if v > 0]
    wanted = [v for v in labels if v <= 52 or (include_bones and v in BONE_LABELS)]
    if not any(v <= 52 for v in labels):
        print(f"  [warn] {seg_path.name}: không có nhãn răng (1-52). "
              "Segmentation này có thể không phải từ model UniversalLab.")

    out_dir = stl_root / case
    out_dir.mkdir(parents=True, exist_ok=True)
    n_exported = 0

    for label in wanted:
        name = LABEL_NAMES.get(label, f"label-{label}")
        if label in BONE_LABELS:
            fname = f"{case}_{sanitize(name)}.stl"
        else:
            fname = f"{case}_UNS{uns_code(label)}_{sanitize(name)}.stl"
        out_path = out_dir / fname

        res = export_labeled_mask(arr == label, matrix, out_path, min_voxels,
                                  smooth_iterations, passband, decimate)
        if res is None:
            continue
        n_tri, volume = res
        n_exported += 1
        manifest_rows.append([case, label, uns_code(label), name,
                              str(out_path.relative_to(stl_root)),
                              n_tri, f"{volume:.1f}"])
        print(f"    + {fname}  ({n_tri} tam giác, {volume:.0f} mm3)")

    return n_exported


# ── Model TotalSegmentator (task "teeth"): răng FDI + xoang hàm + tủy + ống TK ───

def remove_small_islands(mask_zyx: np.ndarray, min_size: int) -> np.ndarray:
    """Xóa các đảo rời nhỏ hơn min_size voxel (như DentalSegmentator của Slicer)."""
    img = sitk.GetImageFromArray(mask_zyx.astype(np.uint8))
    cc = sitk.ConnectedComponent(img)
    relabeled = sitk.RelabelComponent(cc, minimumObjectSize=int(min_size))
    return sitk.GetArrayFromImage(relabeled) > 0


def split_case_dentseg(case: str, seg_path: Path, stl_root: Path,
                       min_voxels: int, smooth_iterations: int, passband: float,
                       decimate: float, manifest_rows: list):
    """Tách 5 nhãn của model DentalSegmentator thành STL.

    Nhãn: Upper-Skull-Maxilla / Mandible / Upper-Teeth / Lower-Teeth /
    Mandibular-canal. Xóa đảo nhiễu nhỏ cho mọi nhãn trừ ống thần kinh.
    """
    img = sitk.ReadImage(str(seg_path))
    arr = sitk.GetArrayFromImage(img)  # (z, y, x)
    matrix = physical_matrix(img)
    labels = [int(v) for v in np.unique(arr) if v > 0]

    out_dir = stl_root / case
    out_dir.mkdir(parents=True, exist_ok=True)
    n_exported = 0

    for label in labels:
        name = DENTSEG_LABELS.get(label, f"label-{label}")
        mask = arr == label
        if label != 5:  # ống thần kinh nhỏ, không lọc kẻo mất
            mask = remove_small_islands(mask, max(min_voxels, 200))
        out_path = out_dir / f"{case}_{sanitize(name)}.stl"
        res = export_labeled_mask(mask, matrix, out_path, min_voxels,
                                  smooth_iterations, passband, decimate)
        if res is None:
            continue
        n_tri, volume = res
        n_exported += 1
        manifest_rows.append([case, label, "", name,
                              str(out_path.relative_to(stl_root)),
                              n_tri, f"{volume:.1f}"])
        print(f"    + {out_path.name}  ({n_tri} tam giác, {volume:.0f} mm3)")

    return n_exported


def read_mask_on_grid(mask_file: Path, ref_img: sitk.Image) -> np.ndarray:
    """Đọc mask nhị phân; nếu lệch lưới ảnh tham chiếu thì resample nearest."""
    timg = sitk.ReadImage(str(mask_file))
    if timg.GetSize() != ref_img.GetSize():
        timg = sitk.Resample(timg, ref_img, sitk.Transform(),
                             sitk.sitkNearestNeighbor, 0, timg.GetPixelID())
    return sitk.GetArrayFromImage(timg) > 0


def _yen_ngua_ke(ws: np.ndarray, dist: np.ndarray):
    """Cặp nhãn kề nhau trong ws -> độ cao "yên ngựa" (mm) tại mặt tiếp xúc.

    Yên ngựa = độ dày lớn nhất của khối tại ranh giới 2 mảnh: tiếp xúc rộng
    (thân-chân cùng răng) cho yên cao, khe hẹp giữa 2 răng cho yên thấp.
    """
    ke = {}
    for ax in range(3):
        s1 = [slice(None)] * 3
        s2 = [slice(None)] * 3
        s1[ax] = slice(0, -1)
        s2[ax] = slice(1, None)
        A, B = ws[tuple(s1)], ws[tuple(s2)]
        m = (A != B) & (A > 0) & (B > 0)
        if not m.any():
            continue
        a, b = A[m].astype(np.int64), B[m].astype(np.int64)
        d = np.minimum(dist[tuple(s1)][m], dist[tuple(s2)][m])
        lo, hi = np.minimum(a, b), np.maximum(a, b)
        key = lo * 1000000 + hi
        order = np.argsort(key)
        key_s, d_s = key[order], d[order]
        uniq, start = np.unique(key_s, return_index=True)
        for i in range(len(uniq)):
            end = start[i + 1] if i + 1 < len(uniq) else len(key_s)
            cap = (int(uniq[i] // 1000000), int(uniq[i] % 1000000))
            s = float(d_s[start[i]:end].max())
            if s > ke.get(cap, -1.0):
                ke[cap] = s
    return ke


def chia_cung_rang(tm_c: np.ndarray, sd_c: np.ndarray, sampling,
                   voxel_mm3: float, min_extra_vox: int):
    """Chia khối răng của 1 hàm thành TỪNG răng (có/không hạt giống FDI).

    1) Marker = hạt giống FDI (răng "có tên") + đỉnh bản đồ khoảng cách ở vùng
       không hạt giống (răng AI sót, "vô danh"); đỉnh lấy nhạy (0.6mm) nên răng
       nhiều chân ban đầu bị chia nhỏ.
    2) Watershed: ranh giới đi theo khe hẹp giữa các mảnh.
    3) GỘP theo yên ngựa: 2 mảnh tiếp xúc RỘNG so với thân (yên ≥ 72% đỉnh
       thấp hơn = thân/chân cùng 1 răng) hoặc mảnh quá nhỏ (<120mm³) thì gộp;
       2 răng FDI khác nhau KHÔNG bao giờ gộp → răng cửa mỏng không dính nhau,
       răng cối nhiều chân không vụn, chân răng ngoài hạt giống về đúng răng.
    Trả về (dict fdi -> mask, list mask răng vô danh) trong lưới đã cắt gọn.
    """
    from scipy import ndimage

    khoi = tm_c | (sd_c > 0)
    if not khoi.any():
        return {}, []
    dist = ndimage.distance_transform_edt(khoi, sampling=sampling)
    dimg = sitk.GetImageFromArray(dist.astype(np.float32))
    peaks = sitk.GetArrayFromImage(
        sitk.RegionalMaxima(sitk.HMaxima(dimg, height=0.6),
                            fullyConnected=True)) > 0
    peaks &= khoi & (sd_c == 0)
    mk = sd_c.astype(np.int32).copy()
    pk_lab, _ = ndimage.label(peaks, structure=np.ones((3, 3, 3), bool))
    vung_pk = (pk_lab > 0) & (mk == 0)
    mk[vung_pk] = pk_lab[vung_pk] + 100          # nhãn vô danh: 101, 102, ...
    nhan = [int(v) for v in np.unique(mk) if v > 0]
    if not nhan:
        return {}, []
    ws = sitk.GetArrayFromImage(sitk.MorphologicalWatershedFromMarkers(
        sitk.GetImageFromArray((-dist).astype(np.float32)),
        sitk.GetImageFromArray(mk), markWatershedLine=False)).astype(np.int32)
    ws[~khoi] = 0
    bc = np.bincount(ws.ravel())
    vol = {l: float(bc[l]) * voxel_mm3 for l in nhan
           if l < len(bc) and bc[l] > 0}
    nhan = [l for l in nhan if l in vol]
    if not nhan:
        return {}, []
    dinh = {l: float(v) for l, v in
            zip(nhan, ndimage.maximum(dist, ws, nhan))}
    yen = _yen_ngua_ke(ws, dist)
    la_fdi = {l: l <= 100 for l in nhan}
    # Tâm (mm) của từng mảnh — để nhận "mảnh chồng dọc" (chân răng nghiêng)
    spz, spy, spx = sampling
    coms = ndimage.center_of_mass(np.ones(ws.shape, np.uint8), ws, nhan)
    tam_yx = {l: (float(cy) * spy, float(cx) * spx)
              for l, (cz, cy, cx) in zip(nhan, coms)}
    tam_z = {l: float(cz) * spz for l, (cz, cy, cx) in zip(nhan, coms)}
    goc = {l: l for l in nhan}

    def find(x):
        while goc[x] != x:
            goc[x] = goc[goc[x]]
            x = goc[x]
        return x

    while True:
        nhom_yen = {}
        for (a, b), s in yen.items():
            if a not in goc or b not in goc:
                continue
            ra, rb = find(a), find(b)
            if ra == rb:
                continue
            cap = (min(ra, rb), max(ra, rb))
            if s > nhom_yen.get(cap, -1.0):
                nhom_yen[cap] = s
        best, best_tl = None, -1.0
        for (ra, rb), s in nhom_yen.items():
            if la_fdi[ra] and la_fdi[rb]:
                continue                          # 2 răng có tên: giữ riêng
            tl = s / max(min(dinh[ra], dinh[rb]), 1e-6)
            (ya, xa), (yb, xb) = tam_yx[ra], tam_yx[rb]
            dxy = float(np.hypot(ya - yb, xa - xb))
            dz = abs(tam_z[ra] - tam_z[rb])
            nho = min(vol[ra], vol[rb])
            # Gộp theo yên rộng: NHƯNG 2 khối đều cỡ răng thật mà tâm cách xa
            # (>4.5mm ngang) là 2 răng chen chúc -> không gộp
            duoc = ((tl >= 0.72 and (dxy < 4.5 or nho < 220.0))
                    or (nho < 120.0 and s > 0.3))
            if not duoc and s > 0.3:
                # Mảnh CHỒNG DỌC: chân/chóp bị cắt rời khỏi thân — hướng nối
                # 2 tâm chủ yếu thẳng đứng (chấp nhận chân răng cửa nghiêng
                # ~20° về vòm miệng: lệch ngang tới 5.5mm) + mảnh nhỏ hơn hẳn
                if (dxy < 5.5 and dz > 1.3 * dxy
                        and nho < 0.62 * max(vol[ra], vol[rb]) and nho < 500.0):
                    duoc, tl = True, max(tl, 0.5)
            if duoc and tl > best_tl:
                best, best_tl = (ra, rb), tl
        if best is None:
            break
        ra, rb = best
        if la_fdi[rb] and not la_fdi[ra]:
            ra, rb = rb, ra                       # giữ nhãn FDI làm gốc
        goc[rb] = ra
        v_a, v_b = vol[ra], vol[rb]
        (ya, xa), (yb, xb) = tam_yx[ra], tam_yx[rb]
        tam_yx[ra] = ((ya * v_a + yb * v_b) / (v_a + v_b),
                      (xa * v_a + xb * v_b) / (v_a + v_b))
        tam_z[ra] = (tam_z[ra] * v_a + tam_z[rb] * v_b) / (v_a + v_b)
        vol[ra] += vol[rb]
        dinh[ra] = max(dinh[ra], dinh[rb])
        la_fdi[ra] = la_fdi[ra] or la_fdi[rb]

    nhoms = {}
    for l in nhan:
        nhoms.setdefault(find(l), []).append(l)
    lut = np.zeros(max(nhan) + 1, np.int32)
    ds_nhom = list(nhoms.items())
    for gi, (r, ls) in enumerate(ds_nhom, 1):
        lut[ls] = gi
    grp = lut[ws]
    fdi_mask, vo_danh = {}, []
    for gi, (r, ls) in enumerate(ds_nhom, 1):
        chon = grp == gi
        if la_fdi[r]:
            fdi = min(x for x in ls if x <= 100)
            fdi_mask[fdi] = chon & (tm_c | (sd_c == fdi))
        else:
            m = chon & tm_c
            if int(m.sum()) >= min_extra_vox:
                vo_danh.append(m)
    return fdi_mask, vo_danh


def _otsu_2_nguong(vals: np.ndarray):
    """Otsu 2 ngưỡng (3 lớp: khí / mô mềm / xương) trên mảng giá trị 1 chiều."""
    hist, edges = np.histogram(vals, bins=128)
    mid = (edges[:-1] + edges[1:]) / 2.0
    p = hist.astype(np.float64)
    tot = p.sum()
    if tot <= 0:
        return None
    p /= tot
    csum_p = np.cumsum(p)
    csum_mu = np.cumsum(p * mid)
    mu_tot = csum_mu[-1]
    best_v, best = -1.0, None
    for i in range(1, 126):
        w0 = csum_p[i]
        if w0 <= 0:
            continue
        m0 = csum_mu[i] / w0
        for j in range(i + 1, 127):
            w1 = csum_p[j] - csum_p[i]
            w2 = 1.0 - csum_p[j]
            if w1 <= 0 or w2 <= 0:
                continue
            m1 = (csum_mu[j] - csum_mu[i]) / w1
            m2 = (mu_tot - csum_mu[j]) / w2
            v = (w0 * (m0 - mu_tot) ** 2 + w1 * (m1 - mu_tot) ** 2
                 + w2 * (m2 - mu_tot) ** 2)
            if v > best_v:
                best_v, best = v, float(edges[i + 1])
    return best


def xoang_du_phong(staged_path: Path, arr: np.ndarray, seeds: np.ndarray,
                   sampling, voxel_mm3: float):
    """Tìm xoang hàm theo hỐC KHÍ khi AI bỏ sót (xoang chỉ lọt 1 phần vào phim).

    Cách làm: bỏ nền đệm ngoài trụ FOV, chia khí/mô bằng Otsu 2 ngưỡng, lấy
    "khí TRONG đầu" = lỗ khí được mô bao kín trên từng lát cắt ngang. Xoang =
    túi khí nằm TRÊN chóp răng hàm trên, lệch khỏi đường giữa (khoang mũi ở
    giữa). Trả về [(mask, tên), ...] — tối đa 2 xoang trái/phải.
    """
    from scipy import ndimage

    try:
        ct_img = sitk.ReadImage(str(staged_path))
        ct = sitk.GetArrayFromImage(ct_img).astype(np.float32)
    except Exception:
        return []
    if ct.shape != arr.shape:
        return []

    up = (arr == 3) | ((seeds >= 11) & (seeds <= 28))
    low = (arr == 2) | (arr == 4) | ((seeds >= 31) & (seeds <= 48))
    if not up.any() or not low.any():
        return []
    z_up = float(np.where(up)[0].mean())
    z_low = float(np.where(low)[0].mean())
    huong = 1.0 if z_up > z_low else -1.0          # chiều "lên trên" theo trục z
    zs_up = np.where(up)[0]
    z_dinh = float(np.percentile(zs_up, 80.0 if huong > 0 else 20.0))  # chóp răng trên

    # Ngưỡng khí/mô: bỏ nền đệm (giá trị đáy) rồi Otsu 2 ngưỡng trong FOV
    ct_min, ct_max = float(ct.min()), float(ct.max())
    t_nen = ct_min + 0.02 * max(ct_max - ct_min, 1e-3)
    mau = ct[::3, ::3, ::3]
    trong_fov = mau[mau > t_nen]
    if trong_fov.size < 1000:
        return []
    t_khi = _otsu_2_nguong(trong_fov)
    if t_khi is None:
        return []
    air = ct <= t_khi                              # khí (gồm cả nền đệm)
    tissue = ~air

    # Khí TRONG đầu: lỗ được mô bao kín trên từng lát cắt ngang
    inside = np.zeros(ct.shape, bool)
    for z in range(ct.shape[0]):
        inside[z] = ndimage.binary_fill_holes(tissue[z]) & air[z]

    # Co ~0.5mm để cắt eo thông mũi-xoang và các khe mỏng
    mm_nho = max(min(sampling), 1e-3)
    n_er = max(1, int(round(0.5 / mm_nho)))
    st = ndimage.generate_binary_structure(3, 1)
    core = ndimage.binary_erosion(inside, st, iterations=n_er, border_value=0)
    lab_c, n_comp = ndimage.label(core, structure=np.ones((3, 3, 3), bool))
    if not n_comp:
        return []

    xs_up = np.where(up)[2]
    x_mid = float(xs_up.mean())                    # đường giữa cung răng (cột x)
    sx_mm = sampling[2]
    ung_vien = []
    for i, slc in enumerate(ndimage.find_objects(lab_c), 1):
        if slc is None:
            continue
        comp = lab_c[slc] == i
        vol = float(comp.sum()) * voxel_mm3
        if vol < 350.0 or vol > 80000.0:
            continue
        idx = np.where(comp)
        zc = slc[0].start + float(idx[0].mean())
        xc = slc[2].start + float(idx[2].mean())
        if (zc - z_dinh) * huong <= 0:
            continue                               # không nằm trên chóp răng trên
        if abs(xc - x_mid) * sx_mm < 7.0:
            continue                               # sát đường giữa = khoang mũi
        ung_vien.append((vol, i, slc, xc))

    ung_vien.sort(reverse=True)                    # to nhất trước
    ket_qua = []
    for vol, i, slc, xc in ung_vien[:2]:
        pad = n_er + 2
        z0 = max(slc[0].start - pad, 0); z1 = min(slc[0].stop + pad, arr.shape[0])
        y0 = max(slc[1].start - pad, 0); y1 = min(slc[1].stop + pad, arr.shape[1])
        x0 = max(slc[2].start - pad, 0); x1 = min(slc[2].stop + pad, arr.shape[2])
        seed = np.zeros((z1 - z0, y1 - y0, x1 - x0), bool)
        sub = (slice(slc[0].start - z0, slc[0].stop - z0),
               (slice(slc[1].start - y0, slc[1].stop - y0)),
               (slice(slc[2].start - x0, slc[2].stop - x0)))
        seed[sub] = lab_c[slc] == i
        phuc_hoi = ndimage.binary_dilation(seed, st, iterations=n_er + 1)
        phuc_hoi &= inside[z0:z1, y0:y1, x0:x1]
        mask = np.zeros(arr.shape, bool)
        mask[z0:z1, y0:y1, x0:x1] = phuc_hoi
        ket_qua.append((mask, xc))

    # Đặt tên trái/phải theo vị trí răng FDI (11-18 = bên phải bệnh nhân)
    x_phai = x_trai = None
    m_p = (seeds >= 11) & (seeds <= 18)
    m_t = (seeds >= 21) & (seeds <= 28)
    if m_p.any():
        x_phai = float(np.where(m_p)[2].mean())
    if m_t.any():
        x_trai = float(np.where(m_t)[2].mean())
    ra = []
    for j, (mask, xc) in enumerate(ket_qua, 1):
        if x_phai is not None and x_trai is not None:
            ten = "Xoang-ham-phai" if abs(xc - x_phai) < abs(xc - x_trai) else "Xoang-ham-trai"
        else:
            ten = f"Xoang-ham-{j}"
        ra.append((mask, ten))
    return ra


def doan_so_fdi(pieces, sd_c, lo, hi, sampling):
    """Đoán số răng FDI cho các răng "vô danh" theo VỊ TRÍ TRÊN CUNG HÀM.

    Cách làm: chiếu tâm mọi răng xuống mặt cắt ngang, khớp đường parabol của
    cung hàm, tính vị trí dọc cung (1-16, phải→trái). ĐẾM TỪ ĐƯỜNG GIỮA RA
    hai bên theo bề rộng giải phẫu từng loại răng (răng 1 sát đường giữa, răng
    8 trong cùng — đúng định nghĩa FDI), kết hợp răng đã có số FDI làm mốc phụ.
    Răng nằm lệch khỏi cung >6mm hoặc lơ lửng (răng ngầm) trả "ngam"; mảnh
    nhỏ <150mm3 trả "manh".
    Trả về danh sách phần tử: (fdi:int) | "ngam" | "manh" | None.
    """
    spz, spy, spx = sampling
    voxel_mm3 = spz * spy * spx
    la_ham_tren = lo == 11

    def vi_tri(fdi):
        q, r = fdi // 10, fdi % 10
        if la_ham_tren:
            return 9 - r if q == 1 else 8 + r
        return 9 - r if q == 4 else 8 + r

    def fdi_cua(p):
        if la_ham_tren:
            return 10 + (9 - p) if p <= 8 else 20 + (p - 8)
        return 40 + (9 - p) if p <= 8 else 30 + (p - 8)

    # Tâm (mm, mặt phẳng ngang y-x + độ cao z) của mốc và của từng mảnh
    moc = []
    for fdi in sorted(int(v) for v in np.unique(sd_c) if v > 0):
        w = np.where(sd_c == fdi)
        moc.append((vi_tri(fdi), float(w[1].mean()) * spy,
                    float(w[2].mean()) * spx, float(w[0].mean()) * spz))
    tam = []
    for m in pieces:
        w = np.where(m)
        tam.append((float(w[1].mean()) * spy, float(w[2].mean()) * spx,
                    float(len(w[0])) * voxel_mm3, float(w[0].mean()) * spz))
    if not moc:
        return [None] * len(pieces)
    # Ứng viên để so ĐỘ CAO cục bộ: mốc AI + mảnh đủ lớn (răng thật gần đó)
    hang_xom = ([(y, x, z, 1e9) for _, y, x, z in moc]
                + [(y, x, z, v) for y, x, v, z in tam if v >= 300.0])

    # Parabol cung hàm y = f(x) qua tất cả răng (mốc + mảnh đủ lớn)
    xs = np.array([x for _, y, x, z in moc]
                  + [x for y, x, v, z in tam if v >= 150.0])
    ys = np.array([y for _, y, x, z in moc]
                  + [y for y, x, v, z in tam if v >= 150.0])
    if len(xs) >= 3 and float(xs.max() - xs.min()) > 5.0:
        he_so = np.polyfit(xs, ys, 2)
    else:
        he_so = np.polyfit(xs, ys, 1) if len(xs) >= 2 else None

    def do_lech(y, x):
        if he_so is None:
            return 0.0
        return abs(y - float(np.polyval(he_so, x)))

    def toa_do_cung(x):
        """Chiều dài cung (mm) từ mép phải đến hoành độ x (dọc parabol)."""
        if he_so is None:
            return x
        x0 = float(xs.min())
        n = max(int(abs(x - x0) / 0.5), 1)
        t = np.linspace(x0, x, n + 1)
        yv = np.polyval(he_so, t)
        return float(np.sum(np.hypot(np.diff(t), np.diff(yv))))

    # Vị trí dọc cung của mốc + BỀ RỘNG giải phẫu từng loại răng (mm, gần-xa)
    s_moc = np.array([toa_do_cung(x) for _, y, x, z in moc])
    p_moc = np.array([p for p, _, _, _ in moc], dtype=float)
    if la_ham_tren:
        rong_r = {1: 8.5, 2: 6.6, 3: 7.6, 4: 7.1, 5: 6.8, 6: 10.7, 7: 10.0, 8: 10.4}
    else:
        rong_r = {1: 5.4, 2: 5.9, 3: 6.9, 4: 7.0, 5: 7.1, 6: 11.0, 7: 10.5, 8: 10.7}

    def rong_p(p):
        return rong_r[9 - p] if p <= 8 else rong_r[p - 8]

    def buoc(p, q):
        return (rong_p(p) + rong_p(q)) / 2.0

    # Chiều tăng của s theo p (hướng đi của cung)
    cap = [(s2 - s1) / (p2 - p1) for (p1, s1), (p2, s2)
           in zip(zip(p_moc, s_moc), zip(p_moc[1:], s_moc[1:]))
           if abs(p2 - p1) > 1e-6]
    chieu = None
    if cap:
        chieu = 1.0 if float(np.median(cap)) >= 0 else -1.0

    # ĐƯỜNG GIỮA — gốc của hệ FDI (răng 1 sát đường giữa, răng 8 trong cùng).
    # Đếm từ giữa ra 2 bên: mỗi bên chỉ cộng dồn sai số qua 8 răng thay vì 16.
    # Ưu tiên: có cả 2 răng cửa giữa > 1 răng cửa giữa > đỉnh parabol cung.
    o_moc = {int(p): float(s) for p, s in zip(p_moc, s_moc)}
    s_giua = None
    if 8 in o_moc and 9 in o_moc:
        s_giua = (o_moc[8] + o_moc[9]) / 2.0
    elif chieu is not None and 8 in o_moc:
        s_giua = o_moc[8] + chieu * rong_p(8) / 2.0
    elif chieu is not None and 9 in o_moc:
        s_giua = o_moc[9] - chieu * rong_p(9) / 2.0
    elif he_so is not None and len(he_so) == 3 and abs(he_so[0]) > 1e-6:
        x_dinh = -he_so[1] / (2.0 * he_so[0])
        if float(xs.min()) - 3.0 <= x_dinh <= float(xs.max()) + 3.0:
            s_giua = toa_do_cung(float(x_dinh))
    if chieu is None and s_giua is not None and len(o_moc) >= 1:
        p0, s0 = next(iter(o_moc.items()))
        d = (s0 - s_giua) * (p0 - 8.5)
        chieu = 1.0 if d >= 0 else -1.0
    if chieu is None:
        return [None] * len(pieces)

    # Tâm dự kiến của 16 ô răng: ĐI BỘ theo bề rộng răng thật (răng cối ~10.5mm,
    # răng cửa ~6mm) từ ĐƯỜNG GIỮA (trọng số cao) và từ từng mốc AI, trọng số
    # giảm theo số răng phải bước qua (càng xa mốc càng kém tin)
    du_kien = {p: [] for p in range(1, 17)}     # p -> [(s, trọng số)]

    def them(p, s, w):
        du_kien[p].append((float(s), float(w)))

    for p0, s0 in zip(p_moc.astype(int), s_moc):
        them(p0, s0, 1e6)
        s = float(s0)
        for q in range(p0 + 1, 17):
            s += chieu * buoc(q - 1, q)
            them(q, s, 1.0 / (1 + q - p0))
        s = float(s0)
        for q in range(p0 - 1, 0, -1):
            s -= chieu * buoc(q + 1, q)
            them(q, s, 1.0 / (1 + p0 - q))
    if s_giua is not None:
        s = s_giua - chieu * rong_p(8) / 2.0
        them(8, s, 2.0)
        for q in range(7, 0, -1):
            s -= chieu * buoc(q + 1, q)
            them(q, s, 2.0 / (1 + 8 - q))
        s = s_giua + chieu * rong_p(9) / 2.0
        them(9, s, 2.0)
        for q in range(10, 17):
            s += chieu * buoc(q - 1, q)
            them(q, s, 2.0 / (1 + q - 9))
    tam_slot = {p: sum(s * w for s, w in v) / sum(w for _, w in v)
                for p, v in du_kien.items() if v}
    con_trong = set(range(1, 17)) - set(int(p) for p in p_moc)

    # Tính s + lọc "manh"/"ngam" cho từng mảnh
    trang_thai = []
    s_manh = []
    for y, x, vol, z in tam:
        if vol < 150.0:
            trang_thai.append("manh")
            s_manh.append(None)
            continue
        # Lệch ngang khỏi cung, hoặc LƠ LỬNG so với răng hàng xóm to nhất
        # trong 9mm (chóp gãy/răng dư nằm trên chân răng khác) -> "ngam"
        lech_z = 0.0
        gan = [(v2, z2) for y2, x2, z2, v2 in hang_xom
               if 0.01 < float(np.hypot(y2 - y, x2 - x)) < 9.0]
        if gan:
            lech_z = abs(z - max(gan)[1])
        if do_lech(y, x) > 6.0 or lech_z > 4.0:
            trang_thai.append("ngam")
            s_manh.append(None)
            continue
        trang_thai.append("cho")
        s_manh.append(toa_do_cung(x))

    # Gán ô GIỮ THỨ TỰ (căn chỉnh chuỗi bằng quy hoạch động): răng xếp theo
    # chiều dài cung phải nhận số tăng dần — không cho răng ngoài "nhảy" vào ô
    # trong khi răng trong còn trống (lỗi của cách tham lam khi cung lệch dần).
    # Dung sai nới dần theo số răng phải bước từ neo gần nhất (mốc AI hoặc
    # đường giữa) — càng xa neo sai số cộng dồn càng lớn
    neo = [float(p) for p in p_moc] + ([8.5] if s_giua is not None else [])

    def dung_sai(p):
        buoc_xa = min(abs(p - a) for a in neo) if neo else 0.0
        return max(0.75 * rong_p(p), 3.5) + 0.6 * buoc_xa

    # Chuỗi A: mốc AI (cố định) + mảnh "cho", sắp theo s tăng dần theo chiều
    A = [("moc", int(p), float(s)) for p, s in zip(p_moc, s_moc)]
    A += [("manh", j, float(s)) for j, (tt, s) in enumerate(zip(trang_thai, s_manh))
          if tt == "cho"]
    A.sort(key=lambda t: chieu * t[2])
    o_list = list(range(1, 17))
    INF = 1e18
    PHAT_BO_MANH = 15.0         # bỏ 1 mảnh không gán (thành Rang-them) — đắt hơn
                                # mọi khớp còn trong dung sai, để ưu tiên xếp số

    def gia(a, p):
        loai, k, s = a
        if loai == "moc":
            return 0.0 if k == p else INF
        if p not in con_trong or p not in tam_slot:
            return INF
        d = abs(s - tam_slot[p])
        return d if d <= dung_sai(p) else INF

    nA, nB = len(A), len(o_list)
    dp = np.full((nA + 1, nB + 1), INF)
    huong = np.zeros((nA + 1, nB + 1), np.int8)   # 1: khớp, 2: bỏ ô, 3: bỏ mảnh
    dp[0, :] = 0.0                                # bỏ ô (răng mất) không tốn
    for i in range(1, nA + 1):
        bo_manh = PHAT_BO_MANH if A[i - 1][0] == "manh" else INF
        for jj in range(0, nB + 1):
            best, h = INF, 0
            if jj > 0:
                c = dp[i - 1, jj - 1] + gia(A[i - 1], o_list[jj - 1])
                if c < best:
                    best, h = c, 1
                if dp[i, jj - 1] < best:
                    best, h = dp[i, jj - 1], 2
            c = dp[i - 1, jj] + bo_manh
            if c < best:
                best, h = c, 3
            dp[i, jj], huong[i, jj] = best, h
    gan_o = {}
    i, jj = nA, nB
    while i > 0 and jj >= 0:
        h = huong[i, jj]
        if h == 1:
            if A[i - 1][0] == "manh":
                gan_o[A[i - 1][1]] = o_list[jj - 1]
            i -= 1; jj -= 1
        elif h == 2:
            jj -= 1
        elif h == 3:
            i -= 1
        else:
            break
    o_da_dung = set(gan_o.values())
    if os.environ.get("DBG_FDI"):
        print("[DBG_FDI] ham", "tren" if la_ham_tren else "duoi", "chieu", chieu,
              "s_giua", None if s_giua is None else round(s_giua, 1))
        print("  moc:", {p: round(s, 1) for p, s in o_moc.items()})
        print("  slot:", {p: round(s, 1) for p, s in sorted(tam_slot.items())})
        for j, (tt, s) in enumerate(zip(trang_thai, s_manh)):
            print(f"  manh {j}: {tt} s={None if s is None else round(s, 1)} "
                  f"vol={round(tam[j][2])}")
    if os.environ.get("DBG_FDI"):
        print("  gan:", {j: (p, fdi_cua(p), round(dung_sai(p), 1)) for j, p in gan_o.items()})
        print("  con trong:", sorted(con_trong - o_da_dung))
    ket_qua = []
    for j, tt in enumerate(trang_thai):
        if tt in ("manh", "ngam"):
            ket_qua.append(tt)
        elif j in gan_o:
            ket_qua.append(fdi_cua(gan_o[j]))
        else:
            ket_qua.append(None)
    return ket_qua


def tien_do_tach(pct: float, msg: str):
    """Dòng tiến độ bước tách răng (GUI đọc để cậ p nhậ t thanh %)."""
    print(f"    [tach] {int(max(0, min(100, pct))):3d}% — {msg}", flush=True)


def split_case_combo(case: str, dentseg_path: Path, totalseg_dir: Path,
                     stl_root: Path, include_pulp: bool, min_voxels: int,
                     smooth_iterations: int, passband: float, decimate: float,
                     manifest_rows: list):
    """Chế độ KẾT HỢP: xương/ống TK từ DentalSegmentator + TỪNG răng FDI từ TotalSeg.

    Khối răng của DentalSegmentator (đầy đủ, bám sát) được chia thành từng răng:
    mỗi voxel răng gán về răng FDI gần nhất của TotalSeg (khoảng cách mm).
    Vùng răng TotalSeg bỏ sót được xuất riêng thành 'Rang-them-*' để không mất răng.
    """
    from scipy import ndimage

    tien_do_tach(0, "đọc kết quả phân đoạn AI")
    img = sitk.ReadImage(str(dentseg_path))
    arr = sitk.GetArrayFromImage(img)  # (z, y, x)
    matrix = physical_matrix(img)
    sx, sy, sz = img.GetSpacing()
    sampling = (sz, sy, sx)            # spacing theo trục numpy (z, y, x)
    voxel_mm3 = sx * sy * sz

    out_dir = stl_root / case
    out_dir.mkdir(parents=True, exist_ok=True)
    # Dọn STL cũ của ca này (kết quả lần trước có thể khác tên → chồng hình cũ/mới)
    for f_cu in out_dir.glob(f"{case}_*.stl"):
        try:
            f_cu.unlink()
        except OSError:
            pass
    n_exported = 0
    # Bản đồ nhãn gộp để cửa sổ "Xem & Sửa" hiển thị/chỉnh/xuất lại
    labelmap = np.zeros(arr.shape, dtype=np.int16)
    label_table = {}

    def _export(mask, fname, label_id, uns, name, lab_id=None):
        nonlocal n_exported
        res = export_labeled_mask(mask, matrix, out_dir / fname, min_voxels,
                                  smooth_iterations, passband, decimate)
        if res is None:
            return
        n_tri, volume = res
        n_exported += 1
        manifest_rows.append([case, label_id, uns, name,
                              str((out_dir / fname).relative_to(stl_root)),
                              n_tri, f"{volume:.1f}"])
        print(f"    + {fname}  ({n_tri} tam giác, {volume:.0f} mm3)")
        if lab_id is not None:
            labelmap[mask] = np.int16(lab_id)
            label_table[int(lab_id)] = fname[len(case) + 1:-4]  # bỏ "case_" và ".stl"

    # 1) Xương hàm + sọ + ống thần kinh: lấy từ DentalSegmentator (bền vững nhất)
    for label in (1, 2, 5):
        mask = arr == label
        if not mask.any():
            continue
        name = DENTSEG_LABELS[label]
        if label != 5:
            mask = remove_small_islands(mask, max(min_voxels, 200))
        _export(mask, f"{case}_{sanitize(name)}.stl", label, "", name, lab_id=label)

    # 2) Hạt giống từng răng FDI (+ xoang hàm, tủy) từ TotalSeg
    tien_do_tach(18, "đọc hạt giống từng răng FDI (TotalSeg)")
    seeds = np.zeros(arr.shape, dtype=np.int16)
    seed_names = {}
    misc_id = 60  # id cho xoang/tủy trong labelmap (61, 62, ...)
    sinus_files = []
    for mask_file in sorted(totalseg_dir.glob("*.nii.gz")):
        cls = mask_file.name[:-7]
        kind = classify_totalseg(cls)
        m = TEETH_FDI_RE.search(cls)
        if kind == "tooth" and m:
            tarr = read_mask_on_grid(mask_file, img)
            if int(tarr.sum()) >= min_voxels:
                fdi = int(m.group(1))
                # Hạt giống chỉ giữ KHỐI LIÊN THÔNG LỚN NHẤT: TotalSeg hay để
                # lạc một mẩu nhỏ sang chân răng kế bên (ca 11186: hạt 46 có
                # mẩu 21mm³ nằm ở chóp 45 -> chóp 45 bị gán nhãn 46)
                cc_s, n_s = ndimage.label(tarr)
                if n_s > 1:
                    sz_s = ndimage.sum(tarr, cc_s, range(1, n_s + 1))
                    tarr = cc_s == (int(np.argmax(sz_s)) + 1)
                seeds[tarr] = fdi
                seed_names[fdi] = TEETH_FDI_RE.sub("", cls).strip("_-") or f"fdi{fdi}"
        elif kind == "sinus":
            sinus_files.append(mask_file)
        elif kind == "pulp" and include_pulp:
            misc_id += 1
            _export(read_mask_on_grid(mask_file, img),
                    f"{case}_{sanitize(cls)}.stl", cls, "", cls, lab_id=misc_id)

    # Xoang hàm: ưu tiên mask trái/phải của task 'teeth'; nếu rỗng dùng
    # mask của task sọ-mặt (sinus_maxillary) để không bỏ sót, không xuất trùng
    tien_do_tach(26, "xuất xoang hàm")
    lr = [f for f in sinus_files
          if f.name[:-7] in ("left_maxillary_sinus", "right_maxillary_sinus")]
    khac = [f for f in sinus_files if f not in lr]

    def _du_lon(f):
        return int(read_mask_on_grid(f, img).sum()) >= max(min_voxels, 500)

    chon = [f for f in lr if _du_lon(f)]
    if not chon:
        chon = [f for f in khac if _du_lon(f)]
    for f in chon:
        cls = f.name[:-7]
        misc_id += 1
        _export(read_mask_on_grid(f, img), f"{case}_{sanitize(cls)}.stl",
                cls, "", cls, lab_id=misc_id)
    if not chon:
        # AI không thấy xoang -> tự tìm theo hốc khí (xoang lọt 1 phần vào phim)
        staged = stl_root.parent / "staged_inputs" / f"{case}.nii.gz"
        du_phong = (xoang_du_phong(staged, arr, seeds, sampling, voxel_mm3)
                    if staged.is_file() else [])
        for mask, ten in du_phong:
            misc_id += 1
            _export(mask, f"{case}_{sanitize(ten)}.stl", ten, "", ten, lab_id=misc_id)
        if du_phong:
            print(f"    [chú ý] xoang hàm: AI bỏ sót — đã lấy {len(du_phong)} xoang theo "
                  "hốc khí (phần thấy được trong phim), kiểm tra lại trong Xem & Sửa")
        else:
            print("    [chú ý] xoang hàm: không tìm thấy trong trường chụp này")

    # 3) Chia khối răng thành từng răng: watershed + gộp theo yên ngựa
    extra_seq = 0
    # Mỗi hàm chiếm 1 nửa khoảng 30..96% của thanh tiến độ bước tách
    for i_ham, (arch_label, lo, hi, arch_vn) in enumerate(((3, 11, 28, "ham-tren"),
                                                          (4, 31, 48, "ham-duoi"))):
        p0 = 30 + i_ham * 33          # điểm đầu % của hàm này
        ten_ham = "hàm trên" if arch_vn == "ham-tren" else "hàm dưới"
        tmask = arr == arch_label
        if not tmask.any():
            tien_do_tach(p0 + 33, f"{ten_ham}: không có răng")
            continue
        tien_do_tach(p0, f"{ten_ham}: chia khối răng thành từng răng (watershed)")
        tmask = remove_small_islands(tmask, max(min_voxels, 200))
        arch_name = DENTSEG_LABELS[arch_label]
        arch_seeds = np.where((seeds >= lo) & (seeds <= hi), seeds,
                              0).astype(np.int16)

        # Cắt gọn quanh vùng răng cho nhẹ RAM
        union = tmask | (arch_seeds > 0)
        if not union.any():
            # Hàm không còn răng (mất răng toàn hàm / chỉ implant): AI chỉ trả vài
            # voxel nhiễu đã bị lọc -> bỏ qua hàm này, KHÔNG làm hỏng cả ca
            print(f"    [chú ý] {arch_vn}: không có răng (AI chỉ thấy nhiễu) — bỏ qua")
            continue
        wz, wy, wx = np.where(union)
        pad = 4
        z0, z1 = max(int(wz.min()) - pad, 0), min(int(wz.max()) + pad, arr.shape[0] - 1)
        y0, y1 = max(int(wy.min()) - pad, 0), min(int(wy.max()) + pad, arr.shape[1] - 1)
        x0, x1 = max(int(wx.min()) - pad, 0), min(int(wx.max()) + pad, arr.shape[2] - 1)
        tm_c = tmask[z0:z1 + 1, y0:y1 + 1, x0:x1 + 1]
        sd_c = arch_seeds[z0:z1 + 1, y0:y1 + 1, x0:x1 + 1]

        min_extra = max(min_voxels, int(100.0 / max(voxel_mm3, 1e-9)))
        fdi_mask, vo_danh = chia_cung_rang(tm_c, sd_c, sampling,
                                           voxel_mm3, min_extra)
        if not fdi_mask and not vo_danh:
            # Không chia được -> xuất nguyên khối như cũ
            _export(tmask, f"{case}_{sanitize(arch_name)}.stl",
                    arch_label, "", arch_name, lab_id=arch_label)
            continue

        # Mảnh nhỏ TREO DỌC phía chân một răng (chóp đứt rời, không chạm)
        # -> ghép vào răng ngay dưới/trên nó thay vì thành "răng" riêng
        spz_, spy_, spx_ = sampling

        def _tam_vol(m):
            w = np.where(m)
            return (float(w[0].mean()) * spz_, float(w[1].mean()) * spy_,
                    float(w[2].mean()) * spx_, float(len(w[0])) * voxel_mm3)

        thong_tin = [_tam_vol(m) for m in vo_danh]
        ung_vien = ([("fdi", f, _tam_vol(fdi_mask[f])) for f in fdi_mask]
                    + [("vd", j, t) for j, t in enumerate(thong_tin)
                       if t[3] >= 300.0])
        giu_lai = []
        for j, (m, (tz, ty, tx, tv)) in enumerate(zip(vo_danh, thong_tin)):
            if tv < 300.0:
                best, best_d = None, 1e9
                # (1) Mảnh CỠ CHÓP (<150mm³) đang CHẠM một răng và nằm DỌC so
                # với răng đó -> ghép vào răng chạm nhiều nhất. Chóp chân răng
                # nghiêng có thể gần TÂM răng kế bên hơn răng của chính nó (ca
                # 45/46: chóp 45 cách tâm 46 4.6mm nhưng cách tâm 45 5.5mm).
                # Răng cửa nhỏ nguyên vẹn (200-260mm³) KHÔNG rơi vào luật này.
                if tv < 150.0:
                    vien = ndimage.binary_dilation(m, np.ones((3, 3, 3), bool)) & ~m
                    best_cham = 0
                    for loai, key, (bz, by, bx, bv) in ung_vien:
                        if loai == "vd" and key == j:
                            continue
                        dxy = float(np.hypot(ty - by, tx - bx))
                        dz = abs(tz - bz)
                        if not (dz > 1.3 * dxy and bv > tv):
                            continue
                        cand = fdi_mask[key] if loai == "fdi" else vo_danh[key]
                        cham = int((vien & cand).sum())
                        if cham > best_cham:
                            best, best_cham = (loai, key), cham
                # (2) Không chạm gì: mảnh TREO DỌC -> răng gần nhất theo tâm
                if best is None:
                    for loai, key, (bz, by, bx, bv) in ung_vien:
                        if loai == "vd" and key == j:
                            continue
                        dxy = float(np.hypot(ty - by, tx - bx))
                        dz = abs(tz - bz)
                        if (dxy < 5.5 and dz > max(4.0, 1.3 * dxy) and bv > tv
                                and dxy < best_d):
                            best, best_d = (loai, key), dxy
                if best is not None:
                    if best[0] == "fdi":
                        fdi_mask[best[1]] |= m
                    else:
                        vo_danh[best[1]] |= m
                    continue
            giu_lai.append(j)
        vo_danh = [vo_danh[j] for j in giu_lai]

        # Xuất từng răng: watershed chiếm ~40% thởi gian của hàm, xuất STL ~60%
        n_rang = len(fdi_mask) + len(vo_danh)
        pa = p0 + 13
        i_rang = 0
        for fdi in sorted(fdi_mask):
            i_rang += 1
            tien_do_tach(pa + 20 * i_rang / max(n_rang, 1),
                         f"{ten_ham}: xuất răng {i_rang}/{n_rang} (FDI {fdi})")
            tooth_c = fdi_mask[fdi]
            seed_vol = int((sd_c == fdi).sum())
            if int(tooth_c.sum()) < max(min_voxels, int(0.2 * seed_vol)):
                # DentalSeg không phủ răng này -> giữ nguyên mask TotalSeg
                tooth_c = tooth_c | (sd_c == fdi)
            mask = np.zeros(arr.shape, dtype=bool)
            mask[z0:z1 + 1, y0:y1 + 1, x0:x1 + 1] = tooth_c
            nm = seed_names.get(fdi, f"fdi{fdi}")
            _export(mask, f"{case}_FDI{fdi}_{sanitize(nm)}.stl", fdi, str(fdi), nm,
                    lab_id=100 + fdi)

        # Răng "vô danh" (TotalSeg bỏ sót): đoán SỐ RĂNG FDI theo vị trí
        # trên cung hàm; răng ngầm/mảnh nhỏ giữ tên riêng để bác sĩ xem lại
        du_doan = doan_so_fdi(vo_danh, sd_c, lo, hi, sampling)
        extra = 0
        n_doan = 0
        for piece, fdi_dd in zip(vo_danh, du_doan):
            extra_seq += 1
            i_rang += 1
            tien_do_tach(pa + 20 * i_rang / max(n_rang, 1),
                         f"{ten_ham}: xuất răng {i_rang}/{n_rang} (AI sót, đoán số)")
            mask = np.zeros(arr.shape, dtype=bool)
            mask[z0:z1 + 1, y0:y1 + 1, x0:x1 + 1] = piece
            if isinstance(fdi_dd, int) and (100 + fdi_dd) not in label_table:
                nm = f"FDI{fdi_dd}-du-doan"
                _export(mask, f"{case}_{nm}.stl", fdi_dd, str(fdi_dd), nm,
                        lab_id=100 + fdi_dd)
                n_doan += 1
                continue
            extra += 1
            if fdi_dd == "ngam":
                nm = f"Rang-ngam-{arch_vn}-{extra}"
            else:
                nm = f"Rang-them-{arch_vn}-{extra}"
            _export(mask, f"{case}_{nm}.stl", "", "", nm, lab_id=200 + extra_seq)
        if n_doan:
            print(f"    [chú ý] {arch_vn}: {n_doan} răng AI sót đã ĐOÁN SỐ FDI theo "
                  "vị trí cung hàm (tên có '-du-doan') — kiểm tra lại số răng")
        if extra:
            print(f"    [chú ý] {arch_vn}: {extra} vùng răng ngầm/mảnh chưa rõ số — "
                  "xem mục 'Rang-ngam/Rang-them' và dùng Gộp vùng nếu cần")

    # 4) Lưu bản đồ nhãn gộp + bảng tên cho cửa sổ "Xem & Sửa"
    if label_table:
        tien_do_tach(97, "lưu bản đồ nhãn cho Xem & Sửa")
        lm_dir = stl_root.parent / "labelmaps"
        lm_dir.mkdir(parents=True, exist_ok=True)
        lm_img = sitk.GetImageFromArray(labelmap)
        lm_img.CopyInformation(img)
        sitk.WriteImage(lm_img, str(lm_dir / f"{case}.nii.gz"), useCompression=True)
        with open(lm_dir / f"{case}.json", "w", encoding="utf-8") as f:
            json.dump({"case": case,
                       "labels": {str(k): v for k, v in sorted(label_table.items())}},
                      f, ensure_ascii=False, indent=1)
        print(f"    -> bản đồ nhãn: labelmaps/{case}.nii.gz (dùng cho Xem & Sửa)")

    tien_do_tach(100, f"xong {n_exported} file STL")
    return n_exported


def classify_totalseg(name: str) -> str:
    """Phân loại class của task 'teeth': tooth / sinus / pulp / other."""
    if "_pulp_" in name:
        return "pulp"
    m = TEETH_FDI_RE.search(name)
    if m and 11 <= int(m.group(1)) <= 48:
        return "tooth"
    if name.endswith("maxillary_sinus") or name in ("sinus_maxillary", "sinus_frontal"):
        return "sinus"
    if name == "head":  # mô mềm toàn đầu, không cần xuất
        return "skip"
    return "other"


def tat_thong_ke_totalseg() -> bool:
    """CHẶN TotalSegmentator gửi thống kê sử dụng ẩn danh (mặc định bật) — 3 lớp:

    1. Ghi ``send_usage_stats = false`` vào ``<TOTALSEG_HOME_DIR|~/.totalsegmentator>/config.json``
       (cách chính thức của tác giả) — bền qua các lần chạy, kể cả khi dùng CLI ngoài.
    2. Thay hàm ``send_usage_stats`` / ``send_usage_stats_application`` trong
       ``totalsegmentator.config`` VÀ bản đã import vào ``python_api`` bằng hàm rỗng
       -> dù config bị bản mới ghi đè cũng không có request nào được tạo.
    3. Không bao giờ gọi các task cần license (không có gói ``license_number``).
    Trả về True nếu chặn được ít nhất lớp 2.
    """
    ok = False
    try:
        import totalsegmentator.config as tc
        try:
            tc.setup_totalseg()
            tc.set_config_key("send_usage_stats", False)
        except Exception as e:                       # thư mục chỉ-đọc... vẫn còn lớp 2
            nhat_ky.log().warning("không ghi được config TotalSegmentator: %s", e)

        def _khong_gui(*_a, **_k):
            return None
        tc.send_usage_stats = _khong_gui
        tc.send_usage_stats_application = _khong_gui
        try:
            import totalsegmentator.python_api as api
            api.send_usage_stats = _khong_gui
        except Exception:
            pass
        ok = True
    except Exception as e:
        nhat_ky.log().warning("không chặn được thống kê TotalSegmentator: %s", e)
    return ok


def run_totalseg(pairs, seg_root: Path, device_str: str, include_bones: bool = False,
                 ensure_sinus: bool = False):
    """Chạy TotalSegmentator task 'teeth' từng ca. Trả về [(case, thư mục mask)].

    ensure_sinus=True: nếu task 'teeth' trả mask xoang hàm RỖNG (hay gặp với
    CBCT trường chụp nhỏ) thì chạy thêm task sọ-mặt để lấy xoang.
    """
    try:
        from totalsegmentator.python_api import totalsegmentator
    except ImportError:
        sys.exit("Thiếu TotalSegmentator. Cài đặt: pip install TotalSegmentator")
    tat_thong_ke_totalseg()

    if device_str == "auto":
        device_str, _, report = auto_config()
        print("  [auto]", report)
    device = "gpu" if device_str == "cuda" else device_str
    seg_root.mkdir(parents=True, exist_ok=True)
    results = []
    for case, staged in pairs:
        case_dir = seg_root / case
        marker = case_dir / "_hoan_tat.txt"
        if marker.is_file():
            print(f"  [skip] {case}: đã có kết quả phân đoạn, bỏ qua")
        else:
            print(f"  [totalseg] {case} (task=teeth, device={device}) ...")
            # nr_thr_saving=1: mặc định 6 tiến trình lưu file song song -> hết RAM
            totalsegmentator(str(staged), str(case_dir), task="teeth", device=device,
                             nr_thr_saving=1)
            if include_bones:
                # Task 'teeth' chỉ phủ vùng quanh răng -> xương hàm bị cắt cụt.
                # Chạy thêm task sọ-mặt để có xương hàm dưới/sọ TRỌN VẸN.
                print(f"  [totalseg] {case} (task=craniofacial_structures) ...")
                totalsegmentator(str(staged), str(case_dir),
                                 task="craniofacial_structures", device=device,
                                 nr_thr_saving=1)
            marker.write_text("xong", encoding="utf-8")
        if ensure_sinus:
            _bo_sung_xoang(totalsegmentator, case, staged, case_dir, device)
        results.append((case, case_dir))
    return results


def _bo_sung_xoang(totalsegmentator, case: str, staged: Path, case_dir: Path,
                   device: str):
    """Task 'teeth' đôi khi trả mask xoang hàm RỖNG -> lấy xoang từ task sọ-mặt."""
    marker = case_dir / "_xoang_hoan_tat.txt"
    if marker.is_file():
        return
    n_vox = 0
    for ten in ("left_maxillary_sinus.nii.gz", "right_maxillary_sinus.nii.gz"):
        f = case_dir / ten
        if f.is_file():
            n_vox += int((sitk.GetArrayFromImage(sitk.ReadImage(str(f))) > 0).sum())
    if n_vox < 1000 and not (case_dir / "sinus_maxillary.nii.gz").is_file():
        print(f"  [totalseg] {case}: xoang hàm trống trong task 'teeth' "
              "-> chạy thêm task sọ-mặt để lấy xoang ...")
        totalsegmentator(str(staged), str(case_dir), task="craniofacial_structures",
                         device=device, nr_thr_saving=1)
    marker.write_text("xong", encoding="utf-8")


def split_case_totalseg(case: str, case_seg_dir: Path, stl_root: Path,
                        include_bones: bool, include_pulp: bool, min_voxels: int,
                        smooth_iterations: int, passband: float, decimate: float,
                        manifest_rows: list):
    """Tách các mask nhị phân của TotalSegmentator (1 file/cấu trúc) thành STL.

    Mặc định xuất: từng răng (FDI 11-48) + xoang hàm trái/phải.
    --include-pulp: thêm tủy từng răng. --include-bones: thêm xương hàm,
    ống thần kinh, hầu họng, cầu/mão răng giả, implant...
    """
    out_dir = stl_root / case
    out_dir.mkdir(parents=True, exist_ok=True)
    n_exported = 0
    # Nếu có xương hàm dưới trọn vẹn (task sọ-mặt) thì bỏ bản cắt cụt của task 'teeth'
    has_full_mandible = (case_seg_dir / "mandible.nii.gz").is_file()

    for mask_file in sorted(case_seg_dir.glob("*.nii.gz")):
        cls = mask_file.name[:-7]  # bỏ ".nii.gz"
        kind = classify_totalseg(cls)
        if kind == "skip":
            continue
        if has_full_mandible and cls == "lower_jawbone":
            continue
        if kind == "pulp" and not include_pulp:
            continue
        if kind == "other" and not include_bones:
            continue

        img = sitk.ReadImage(str(mask_file))
        arr = sitk.GetArrayViewFromImage(img)
        m = TEETH_FDI_RE.search(cls)
        if kind == "tooth" and m:
            fname = f"{case}_FDI{m.group(1)}_{sanitize(TEETH_FDI_RE.sub('', cls))}.stl"
        else:
            fname = f"{case}_{sanitize(cls)}.stl"
        out_path = out_dir / fname

        res = export_labeled_mask(arr > 0, physical_matrix(img), out_path,
                                  min_voxels, smooth_iterations, passband, decimate)
        if res is None:
            continue
        n_tri, volume = res
        n_exported += 1
        manifest_rows.append([case, cls, (m.group(1) if kind == "tooth" and m else ""),
                              cls, str(out_path.relative_to(stl_root)),
                              n_tri, f"{volume:.1f}"])
        print(f"    + {fname}  ({n_tri} tam giác, {volume:.0f} mm3)")

    if n_exported == 0:
        print(f"  [warn] {case}: không có cấu trúc nào đủ lớn để xuất")
    return n_exported


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="Tách từng răng từ CBCT thành file STL riêng (tự động hoàn toàn).")
    ap.add_argument("-i", "--input", required=True, help="Thư mục CBCT (hoặc thư mục segmentation nếu --seg-only)")
    ap.add_argument("-o", "--output", required=True, help="Thư mục kết quả")
    ap.add_argument("--seg-only", action="store_true",
                    help="Input đã là kết quả phân đoạn, bỏ qua bước AI")
    ap.add_argument("--model", default="universallab",
                    choices=["universallab", "totalseg", "dentseg", "combo"],
                    help="universallab: 55 nhãn răng+xương hàm | totalseg: "
                         "TotalSegmentator task 'teeth' — răng FDI + XOANG HÀM "
                         "trái/phải + ống thần kinh + tủy răng | dentseg: "
                         "DentalSegmentator (453 ca CT/CBCT đa trung tâm) — "
                         "2 hàm + răng trên/dưới + ống TK, BỀN VỮNG nhất | "
                         "combo: KẾT HỢP — xương/khối răng DentalSegmentator "
                         "chia thành TỪNG răng theo số FDI của TotalSeg")
    ap.add_argument("--include-bones", action="store_true",
                    help="Xuất thêm xương hàm/ống thần kinh (universallab) hoặc "
                         "các cấu trúc khác: xương hàm, hầu họng, implant... (totalseg)")
    ap.add_argument("--include-pulp", action="store_true",
                    help="(totalseg) Xuất thêm tủy của từng răng")
    ap.add_argument("--device", default="auto", choices=["auto", "cuda", "cpu"],
                    help="auto: tự đánh giá GPU/VRAM/RAM và chọn cấu hình tối ưu")
    ap.add_argument("--model-dir", default=None,
                    help="Thư mục model nnUNet (mặc định: <gốc dự án>/models/<tên model>, "
                         "đổi bằng config.json hoặc biến môi trường TACHRANG_MODELS)")
    ap.add_argument("--smooth-iterations", type=int, default=15)
    ap.add_argument("--passband", type=float, default=0.01)
    ap.add_argument("--decimate", type=float, default=0.0,
                    help="Giảm số tam giác 0-0.95 (0 = tắt)")
    ap.add_argument("--min-voxels", type=int, default=50,
                    help="Bỏ qua nhãn nhỏ hơn số voxel này (lọc nhiễu)")
    ap.add_argument("--single-case", action="store_true",
                    help="Coi thư mục input là DICOM của MỘT bệnh nhân duy nhất "
                         "(tên ca = tên thư mục)")
    args = ap.parse_args()

    log_file = nhat_ky.bat_dau_log("pipeline")
    nhat_ky.log().info("lệnh: %s", " ".join(sys.argv))
    print(f"  [log] {log_file}")
    try:
        _chay(args)
    except SystemExit as e:
        if e.code not in (None, 0):
            msg = str(e.code) if not isinstance(e.code, int) else f"mã {e.code}"
            nhat_ky.log().error("thoát: %s", msg)
            if not isinstance(e.code, int):
                print(f"\n{nhat_ky.DAU_LOI} {msg}")
                print(f"{nhat_ky.DAU_LOG} {log_file}")
                sys.exit(2)
        raise
    except KeyboardInterrupt:
        print(f"\n{nhat_ky.DAU_LOI} Đã dừng theo yêu cầu.")
        sys.exit(130)
    except BaseException as e:  # noqa: BLE001 — mọi lỗi đều phải ra hộp thoại dễ hiểu
        nhat_ky.bao_loi(e, "pipeline")
        sys.exit(2)


def _chay(args):
    input_dir = Path(args.input)
    output_dir = Path(args.output)
    if not input_dir.is_dir():
        sys.exit(f"Không tìm thấy thư mục input: {input_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    stl_root = output_dir / "stl"

    if args.seg_only:
        if args.model == "combo":
            # Input = thư mục kết quả cũ có segmentations_dentseg + segmentations_totalseg
            dent_dir = input_dir / "segmentations_dentseg"
            tot_root = input_dir / "segmentations_totalseg"
            seg_paths = []
            if dent_dir.is_dir():
                for p in sorted(dent_dir.glob("*.nii.gz")):
                    case = sanitize(case_stem(p))
                    if (tot_root / case).is_dir():
                        seg_paths.append((case, (p, tot_root / case)))
        elif args.model == "totalseg":
            # Mỗi ca = 1 thư mục con chứa các mask nhị phân *.nii.gz
            seg_paths = [(sanitize(d.name), d) for d in sorted(input_dir.iterdir())
                         if d.is_dir() and any(d.glob("*.nii.gz"))]
            if not seg_paths and any(input_dir.glob("*.nii.gz")):
                seg_paths = [(sanitize(input_dir.name), input_dir)]
        else:
            seg_paths = [(sanitize(case_stem(p)), p)
                         for p in sorted(input_dir.iterdir())
                         if p.is_file() and p.name.lower().endswith(IMG_EXTS)]
        if not seg_paths:
            sys.exit("Không tìm thấy file segmentation nào trong thư mục input.")
    else:
        print("[1/3] Chuẩn hoá dữ liệu input ...")
        if args.single_case:
            pairs = stage_single_case(input_dir, output_dir / "staged_inputs")
        else:
            pairs = stage_inputs(input_dir, output_dir / "staged_inputs")
        if not pairs:
            sys.exit("Không tìm thấy ảnh CBCT nào (file .nii/.nrrd/... hoặc thư mục DICOM).")
        print(f"      {len(pairs)} ca: {', '.join(c for c, _ in pairs)}")

        if args.model == "totalseg":
            print("[2/3] Phân đoạn AI (TotalSegmentator task 'teeth': răng + xoang hàm) ...")
            seg_paths = run_totalseg(pairs, output_dir / "segmentations_totalseg", args.device,
                                     include_bones=args.include_bones)
        elif args.model == "combo":
            print("[2/3] Phân đoạn AI (KẾT HỢP: DentalSegmentator + TotalSeg răng FDI) ...")
            model_dir = Path(args.model_dir) if args.model_dir else (
                cau_hinh.thu_muc_models("DentalSegmentator"))
            download_model_dentseg(model_dir)
            dent_map = dict(run_inference(pairs, output_dir / "segmentations_dentseg",
                                          model_dir, args.device))
            tot_map = dict(run_totalseg(pairs, output_dir / "segmentations_totalseg",
                                        args.device, ensure_sinus=True))
            seg_paths = [(case, (dent_map[case], tot_map[case]))
                         for case, _ in pairs if case in dent_map and case in tot_map]
        elif args.model == "dentseg":
            print("[2/3] Phân đoạn AI (DentalSegmentator: 2 hàm + răng + ống TK) ...")
            model_dir = Path(args.model_dir) if args.model_dir else (
                cau_hinh.thu_muc_models("DentalSegmentator"))
            download_model_dentseg(model_dir)
            seg_paths = run_inference(pairs, output_dir / "segmentations_dentseg", model_dir, args.device)
        else:
            print("[2/3] Phân đoạn AI (UniversalLabDentalsegmentator) ...")
            model_dir = Path(args.model_dir) if args.model_dir else (
                cau_hinh.thu_muc_models("UniversalLab"))
            download_model(model_dir)
            seg_paths = run_inference(pairs, output_dir / "segmentations", model_dir, args.device)

    print("[3/3] Tách từng răng thành STL ...")
    manifest_rows = []
    total = 0
    for i_ca, (case, seg_path) in enumerate(seg_paths):
        print(f"  {case}:")
        print(f"    [tach-ca] {i_ca + 1}/{len(seg_paths)}", flush=True)
        try:
            if args.model == "combo":
                dent_path, tdir = seg_path
                total += split_case_combo(case, dent_path, tdir, stl_root,
                                          args.include_pulp, args.min_voxels,
                                          args.smooth_iterations, args.passband,
                                          args.decimate, manifest_rows)
            elif args.model == "totalseg":
                total += split_case_totalseg(case, seg_path, stl_root,
                                             args.include_bones, args.include_pulp,
                                             args.min_voxels, args.smooth_iterations,
                                             args.passband, args.decimate, manifest_rows)
            elif args.model == "dentseg":
                total += split_case_dentseg(case, seg_path, stl_root,
                                            args.min_voxels, args.smooth_iterations,
                                            args.passband, args.decimate, manifest_rows)
            else:
                total += split_case(case, seg_path, stl_root, args.include_bones,
                                    args.min_voxels, args.smooth_iterations,
                                    args.passband, args.decimate, manifest_rows)
        except Exception as e:  # 1 ca lỗi không làm hỏng cả batch
            nhat_ky.log().exception("tách STL ca %s", case)
            print(f"  [error] {case}: {nhat_ky.giai_thich(e)}")

    if manifest_rows:
        manifest = stl_root / "manifest.csv"
        with open(manifest, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["case", "label", "uns", "name", "file", "triangles", "volume_mm3"])
            w.writerows(manifest_rows)
        print(f"\nXong: {total} file STL trong {stl_root}")
        print(f"Danh sách chi tiết: {manifest}")
    else:
        print("\nKhông xuất được file nào — kiểm tra lại dữ liệu input.")


if __name__ == "__main__":
    main()
