# -*- coding: utf-8 -*-
"""Thống kê opcode lệnh facets trong các DCM gốc của 3Shape (để biết bộ lệnh 3Shape thật sự dùng)."""
import sys
from pathlib import Path
from collections import Counter
import numpy as np
from hpsdecode import load_hps

for p in sys.argv[1:]:
    p = Path(p)
    packed, mesh = load_hps(str(p))
    cmds = getattr(packed, "face_commands", None)
    if cmds is None:
        # thử lấy qua parser trực tiếp
        from hpsdecode.schemas.cc import CCSchemaParser, IndexMode
        import re, base64
        s = p.read_bytes().decode("latin1")
        fb = base64.b64decode(re.search(r"<Facets[^>]*>([^<]*)</Facets>", s).group(1))
        fc = int(re.search(r'facet_count="(\d+)"', s).group(1))
        par = CCSchemaParser()
        for mode in (IndexMode.MODE_16BIT, IndexMode.MODE_32BIT):
            try:
                par._clear(); cmds = par._parse_commands(fb, mode)
                for c in cmds: par._process_command(c, len(mesh.vertices))
                if len(par._faces) == fc:
                    print(f"{p.name}: mode {mode.name} OK"); break
            except Exception as e:
                cmds = None
    ops = Counter(type(c).__name__ for c in cmds)
    print(f"{p.name}: V={len(mesh.vertices)} F={len(mesh.faces)} lệnh={len(cmds)} → {dict(ops)}")
    # payload của Absolute16/Restart16: giá trị tối đa
    mx = max([getattr(c, "v", 0) for c in cmds] + [0])
    print(f"   chỉ số tuyệt đối lớn nhất trong Absolute: {mx}")
