# -*- coding: utf-8 -*-
"""In N lá»‡nh Ä‘áº§u cá»§a stream facets (kÃ¨m tráº¡ng thÃ¡i mÃ¡y) Ä‘á»ƒ so 3Shape gá»‘c vs cá»§a tÃ´i."""
import sys, re, base64
from pathlib import Path
from hpsdecode.schemas.cc import CCSchemaParser, IndexMode

p = Path(sys.argv[1]); N = int(sys.argv[2]) if len(sys.argv) > 2 else 80
s = p.read_bytes().decode("latin1")
fb = base64.b64decode(re.search(r"<Facets[^>]*>([^<]*)</Facets>", s).group(1))
par = CCSchemaParser(); par._clear()
cmds = par._parse_commands(fb, IndexMode.MODE_32BIT)
par._clear()
print("bytes Ä‘áº§u:", fb[:40].hex())
for k, c in enumerate(cmds[:N]):
    E = par._edge_list; n = len(E); ci = par._current_edge_idx
    ctx = f"n={n:3d} cur={ci:3d}"
    if n:
        ce = E[ci]; ctx += f" cur=({ce.start}->{ce.end}) prev=({E[(ci-1)%n].start}->{E[(ci-1)%n].end}) next=({E[(ci+1)%n].start}->{E[(ci+1)%n].end})"
    nf = len(par._faces)
    par._process_command(c, None)
    face = par._faces[nf] if len(par._faces) > nf else ""
    print(f"{k:3d} {type(c).__name__:11s} {getattr(c,'v',''):>6} | {ctx} | face {face}")

