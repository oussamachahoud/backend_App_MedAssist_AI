"""
convert_notebooks.py
Converts all .ipynb files in the notebooks/ directory to clean .py scripts.
Uses only stdlib + json — no jupyter/nbconvert needed.
"""
import json, os, pathlib, textwrap, re

SRC_DIR  = pathlib.Path("notebooks")
DST_DIR  = pathlib.Path("notebooks/py_exports")
DST_DIR.mkdir(exist_ok=True)

for nb_path in sorted(SRC_DIR.glob("*.ipynb")):
    try:
        nb = json.loads(nb_path.read_text(encoding="utf-8", errors="replace"))
    except Exception as e:
        print(f"  SKIP {nb_path.name}: {e}")
        continue

    lines = [f"# ═══ NOTEBOOK: {nb_path.name} ═══\n"]
    for i, cell in enumerate(nb.get("cells", [])):
        ctype  = cell.get("cell_type", "")
        source = "".join(cell.get("source", []))
        if not source.strip():
            continue

        if ctype == "markdown":
            # Wrap markdown as block comments
            lines.append(f"\n# {'─'*60}")
            for ln in source.splitlines():
                lines.append(f"# {ln}")
            lines.append("")
        elif ctype == "code":
            lines.append(f"\n# ── Cell {i+1} ───────────────────────────────────────")
            lines.append(source if source.endswith("\n") else source + "\n")

    dst = DST_DIR / (nb_path.stem + ".py")
    dst.write_text("\n".join(lines), encoding="utf-8")
    print(f"  OK  {nb_path.name}  ->  {dst.name}  ({len(lines)} lines)")

print("\nDone. Files in:", DST_DIR.resolve())
