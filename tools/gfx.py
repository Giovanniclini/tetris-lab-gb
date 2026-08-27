"""Convert the original game's PNGs to Game Boy tile data.

Every output has an explicitly declared expected size, asserted after conversion.
This is deliberate: rgbgfx output length depends on the PNG's padded dimensions,
and a wrong size surfaces later as an opaque "section overlaps" link error.
(kaspermeerts/tetris cannot be built at all because its Makefile omits these
rules; see docs/research.md section 6.)
"""

import subprocess
from pathlib import Path

# name -> (source png, extra rgbgfx args, expected output bytes)
GFX = {
    "titleScreen.2bpp": ("gfx/2bpp/titleScreen.png", ["-x", "9"], 1904),
    "menuScreens.2bpp": ("gfx/2bpp/menuScreens.png", ["-x", "11"], 3152),
    "rocketScene.2bpp": ("gfx/2bpp/rocketScene.png", [], 3328),
    "ascii.1bpp": ("gfx/1bpp/ascii.png", ["-d", "1"], 312),
}

# Lab graphics, converted the same way. Kept separate because src/original/ is
# vendored: nothing here may change a byte of the LAB=0 build.
LAB_GFX = {
    "labTitleScreen.2bpp": ("../lab/gfx/2bpp/labTitleScreen.png", [], 2048),
}


def build(rgbgfx: Path, src_dir: Path, out_dir: Path, lab: bool = True) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    todo = dict(GFX)
    if lab:
        todo.update({k: (v[0], v[1], v[2]) for k, v in LAB_GFX.items()})
    for name, (png, args, expected) in todo.items():
        out = out_dir / name
        src = src_dir / png
        if not src.exists():
            raise SystemExit(f"missing graphics source: {src}")
        subprocess.run(
            [str(rgbgfx), "-o", str(out), str(src), *args], check=True
        )
        size = out.stat().st_size
        if size != expected:
            raise SystemExit(
                f"{name}: expected {expected} bytes, got {size}.\n"
                f"  rgbgfx output size changed - check the toolchain version "
                f"before touching the expected value."
            )
