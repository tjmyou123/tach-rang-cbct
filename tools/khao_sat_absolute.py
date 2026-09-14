# -*- coding: utf-8 -*-
"""Ngá»¯ cáº£nh cÃ¡c lá»‡nh Absolute16 trong stream: v so vá»›i con trá» Ä‘á»‰nh toÃ n cá»¥c, v cÃ³ trong danh sÃ¡ch cáº¡nh hiá»‡n táº¡i khÃ´ng."""
import sys, re, base64
from pathlib import Path
from collections import Counter
from hpsdecode.schemas.cc import CCSchemaParser, IndexMode

p = Path(sys.argv[1]); N = int(sys.argv[2]) if len(sys.argv) > 2 else 15
s = p.read_bytes().decode("latin1")
fb = base64.b64decode(re.search(r"<Facets[^>]*>([^<]*)</Facets>", s).group(1))
par = CCSchemaParser(); par._clear()
cmds = par._parse_commands(fb, IndexMode.MODE_32BIT)
par._clear()
k_abs = 0
stat = Counter()
for k, c in enumerate(cmds):
    if type(c).__name__ == "Absolute16":
        E = par._edge_list; n = len(E); ci = par._current_edge_idx
        ce = E[ci]
        in_edges = [i for i, ed in enumerate(E) if ed.start == c.v or ed.end == c.v]
        rel = [(i - ci) % n for i in in_edges]
        ptr = par._global_vertex_ptr
        stat[("v<ptr" if c.v < ptr else "v>=ptr", "trong-vong" if in_edges else "ngoai-vong")] += 1
        if k_abs < N:
            print(f"lá»‡nh {k}: Absolute16 v={c.v} ptr={ptr} n={n} cur=({ce.start}->{ce.end}) v náº±m á»Ÿ cáº¡nh (lá»‡ch so cur): {rel[:6]}")
        k_abs += 1
    par._process_command(c, None)
print("tá»•ng:", dict(stat))

