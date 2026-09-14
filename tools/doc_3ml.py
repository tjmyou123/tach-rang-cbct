# -*- coding: utf-8 -*-
"""Giải nén .3ml (zip chứa XML) của 3Shape Ortho và rút gọn base64 để đọc."""
import re, sys, zipfile
from collections import Counter
from pathlib import Path
p = Path(sys.argv[1])
z = zipfile.ZipFile(p)
for i in z.infolist():
    print(i.filename, i.file_size)
s = z.read(z.infolist()[0].filename).decode("utf-8", "replace")
out = re.sub(r">([A-Za-z0-9+/=\s]{120,})<", lambda m: ">[B64 %d]<" % len(m.group(1)), s)
dst = p.with_name(p.stem + "_rutgon.xml")
dst.write_text(out, encoding="utf-8")
print("->", dst, len(s), "→", len(out))
print(Counter(re.findall(r"<(\w+)", out)).most_common(25))
print(Counter(re.findall(r'type="(\w+)"', out)).most_common(60))
