# -*- coding: utf-8 -*-
"""PhÃ¢n tÃ­ch NGá»® Cáº¢NH lá»‡nh trong stream facets gá»‘c cá»§a 3Shape (Ä‘á»ƒ encoder chá»‰ dÃ¹ng Ä‘Ãºng cÃ¡c tÃ¬nh huá»‘ng Ä‘Ã³)."""
import sys, re, base64
from pathlib import Path
from collections import Counter
import numpy as np
from hpsdecode.schemas.cc import CCSchemaParser, IndexMode
import hpsdecode.commands as hpc

p = Path(sys.argv[1])
s = p.read_bytes().decode("latin1")
fb = base64.b64decode(re.search(r"<Facets[^>]*>([^<]*)</Facets>", s).group(1))
fc = int(re.search(r'facet_count="(\d+)"', s).group(1))
par = CCSchemaParser(); par._clear()
cmds = par._parse_commands(fb, IndexMode.MODE_32BIT)
# táº­p cáº¡nh cÃ³ hÆ°á»›ng cá»§a lÆ°á»›i cuá»‘i (Ä‘á»ƒ biáº¿t cáº¡nh "cháº¿t")
par2 = CCSchemaParser(); par2._clear()
for c in cmds: par2._process_command(c, None)
F = np.array(par2._faces)
mat = {}
for fi, (a, b, c) in enumerate(F):
    mat[(a, b)] = fi; mat[(b, c)] = fi; mat[(c, a)] = fi
par._clear()
done = set()
ctx = Counter()
n_hist = Counter()
for k, c in enumerate(cmds):
    E = par._edge_list; n = len(E); ci = par._current_edge_idx
    if n:
        ce = E[ci]; pe = E[(ci - 1) % n]
        fi = mat.get((ce.end, ce.start)); song = fi is not None and fi not in done
        spike = pe.start == ce.end
        pfi = mat.get((pe.end, pe.start)); prev_song = pfi is not None and pfi not in done
        lien_tuc = pe.end == ce.start
    name = type(c).__name__
    if name == "Remove":
        ctx[("Remove", "spike" if spike else "no-spike", "cur_song" if song else "cur_chet", "prev_song" if prev_song else "prev_chet", "n>2" if n > 2 else f"n={n}")] += 1
    elif name == "Ignore":
        ctx[("Ignore", "cur_song" if song else "cur_chet", "prev_song" if prev_song else "prev_chet", "spike" if spike else "")] += 1
    elif name in ("Previous", "Next", "VertexList", "Absolute16"):
        ctx[(name, "cur_song" if song else "cur_chet")] += 1
    if name in ("Previous", "Next"):
        n_hist[min(n, 6)] += 1
    n0 = len(par._faces)
    par._process_command(c, None)
    for f in range(n0, len(par._faces)):
        done.add(f)
for k, v in sorted(ctx.items(), key=lambda kv: -kv[1]):
    print(v, k)
print("kÃ­ch cá»¡ edge list khi Previous/Next (â‰¤6):", dict(n_hist))

