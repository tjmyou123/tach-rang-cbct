# -*- coding: utf-8 -*-
"""So model set 3Shape hiện tại với bản backup đã ghép: file nào bị 3Shape ghi lại, schema, số facet."""
import re, sys
from pathlib import Path
from datetime import datetime
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tachrang.core.kho_3shape import schema_dcm

live = Path(r"C:\ProgramData\3Shape\OrthoData\1222\1")
bk = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"e:\dental segment\backup_3shape\1222_20260908_174218\1")


def facets(p):
    s = p.read_bytes()[:600].decode("latin1")
    m = re.search(r'facet_count="(\d+)"', s)
    return int(m.group(1)) if m else None


print(f"{'file':22s} {'schema':6s} {'facet live':>10s} {'facet ghép':>10s} {'mtime live':19s}  đổi?")
for f in sorted(live.glob("Tooth_*.dcm"), key=lambda p: int(re.search(r"\d+", p.name).group()) if re.search(r"Tooth_(\d+)", p.name) else 99):
    b = bk / f.name
    fl, fb = facets(f), facets(b) if b.exists() else None
    mt = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    doi = "GHI LẠI" if (b.exists() and f.stat().st_size != b.stat().st_size) else ""
    print(f"{f.name:22s} {schema_dcm(f):6s} {fl!s:>10s} {fb!s:>10s} {mt}  {doi}")
for n in ("Tooth_UpperJaw.dcm", "Tooth_LowerJaw.dcm", "Maxillary.dcm", "Mandibular.dcm", "OrthoModellingTree.3ml"):
    f = live / n
    if f.exists():
        print(f"{n:22s} {schema_dcm(f) if n.endswith('.dcm') else '-':6s} {'':>10s} {'':>10s} "
              f"{datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')}  "
              f"{'GHI LẠI' if (bk / n).exists() and f.stat().st_size != (bk / n).stat().st_size else ''}")
