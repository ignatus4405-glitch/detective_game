#!/usr/bin/env python
"""Генерация version_info.txt и манифеста с текущей версией из VERSION."""
import re
from pathlib import Path

root = Path(__file__).parent.parent
version_file = root / "VERSION"
version = version_file.read_text(encoding="utf-8").strip().lstrip("vV")
parts = version.split(".")
while len(parts) < 4:
    parts.append("0")
nums = tuple(int(p) for p in parts[:4])
version_str = version
nums_str = ",".join(str(n) for n in nums)

# version_info.txt
tpl = Path(__file__).parent / "version_info.txt"
text = tpl.read_text(encoding="utf-8")
# robust: replace any filevers/prodvers tuple
text = re.sub(r"filevers=\([^)]+\)", f"filevers=({nums_str})", text)
text = re.sub(r"prodvers=\([^)]+\)", f"prodvers=({nums_str})", text)
text = re.sub(r"FileVersion', u'[^']+'", f"FileVersion', u'{version_str}'", text)
text = re.sub(r"ProductVersion', u'[^']+'", f"ProductVersion', u'{version_str}'", text)

generated = root / "build_version_info.txt"
generated.write_text(text, encoding="utf-8")
print(f"Generated {generated}: {version_str} -> {nums_str}")

# manifest
manifest_tpl = Path(__file__).parent / "app.manifest"
mt = manifest_tpl.read_text(encoding="utf-8")
# только assemblyIdentity, не трогаем <?xml version="1.0"?>
mt = re.sub(r'(<assemblyIdentity[^>]*\n\s+version=")[^"]+"', rf'\g<1>{version_str}.0"', mt)
generated_mf = root / "build_app.manifest"
generated_mf.write_text(mt, encoding="utf-8")
print(f"Generated {generated_mf}")
