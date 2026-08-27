#!/usr/bin/env python3
"""Regenerate the README's screenshots from the ROM.

    .venv/bin/python tools/screenshots.py

Drives the built ROM to each screen and writes assets/screens/*.png. Needs
PyBoy, the same test-only dependency the behavioural tests use; the PNGs are
written with the standard library, so there is nothing else to install.

Kept as a script rather than committed one-off captures: the screens change, and
a picture of last month's menu is worse than none.
"""

import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.emu import (Tetris, hATypeLevel, GS_IN_GAME_MAIN,  # noqa: E402
                       GS_A_TYPE_SELECTION_MAIN)

OUT = ROOT / "assets" / "screens"
SCALE = 3

# The DMG palette PyBoy renders in monochrome; map all four levels onto the
# familiar green so the shots look like a Game Boy rather than a fax. Four, not
# two: the title artwork uses every shade, and a lookup that knew only black and
# white rendered both mid-greys as black.
GREEN = {
    0xFF: (0x9B, 0xBC, 0x0F),
    0x99: (0x8B, 0xAC, 0x0F),
    0x55: (0x30, 0x62, 0x30),
    0x00: (0x0F, 0x38, 0x0F),
}

MODE_TETRIS, MODE_BTYPE, MODE_TRANSITION, MODE_CRUNCH, MODE_SEED, MODE_MUSIC = range(6)

PICKER_CELL = 0x9800 + 6 * 32 + 16
TILE_BLANK = 0x2F


def write_png(path, rgb_rows, width, height):
    raw = b"".join(b"\x00" + row for row in rgb_rows)

    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def shoot(t, name):
    fb = t.pb.screen.ndarray
    h, w = len(fb), len(fb[0])
    rows = []
    for y in range(h):
        row = bytearray()
        for x in range(w):
            r, g, b = GREEN.get(int(fb[y][x][0]), GREEN[0x00])
            row += bytes((r, g, b)) * SCALE
        rows.extend([bytes(row)] * SCALE)
    OUT.mkdir(parents=True, exist_ok=True)
    write_png(OUT / f"{name}.png", rows, w * SCALE, h * SCALE)
    print(f"  assets/screens/{name}.png")


def goto(t, row, mode_addr):
    for _ in range(8):
        if t[mode_addr] == row:
            return
        t.press("down" if t[mode_addr] < row else "up")


def main():
    from tools.emu import sym

    mode = sym("wLabMode")
    print("screenshots:")

    with Tetris("build/tetrislab.gb") as t:
        t.to_title()
        t.tick(20)
        shoot(t, "title")

        t.to_menu()
        shoot(t, "menu")

        goto(t, MODE_CRUNCH, mode)
        for _ in range(10):                 # $A - two columns off each side
            t.press("right")
        shoot(t, "crunch-menu")
        t.press("start")
        t.run_until_state(GS_A_TYPE_SELECTION_MAIN)
        t.press("start")
        t.run_until_state(GS_IN_GAME_MAIN)
        t.tick(60)
        shoot(t, "crunch")

    with Tetris("build/tetrislab.gb") as t:
        t.to_menu()
        goto(t, MODE_SEED, mode)
        t.press("a")
        for nibble in (0xA, 0xC, 0xE, 0x1):
            for _ in range(nibble):
                t.press("up")
            t.press("right")
        t.press("a")
        shoot(t, "seed")

        goto(t, MODE_TRANSITION, mode)
        for _ in range(9):
            t.press("right")
        shoot(t, "transition-menu")

        # TRANSITION takes its level from the level select, like every other
        # trainer, so starting it is two presses and not one. Level 9 is the
        # drill worth a picture: it starts on 90 lines, ten from transition.
        t.press("start")
        t.run_until_state(GS_A_TYPE_SELECTION_MAIN)
        while t[hATypeLevel] < 9:
            t.press("right")
        t.press("start")
        t.run_until_state(GS_IN_GAME_MAIN)
        t.tick(40)
        shoot(t, "transition")

    with Tetris("build/tetrislab.gb") as t:
        t.to_level_select()
        t.press("select")                       # hearts on
        while t[hATypeLevel] < 9:
            t.press("right")
        t.press("right")                        # into the picker, which opens at A
        for _ in range(60):                     # catch the picker on a lit blink
            t.tick(1)
            if t[PICKER_CELL] != TILE_BLANK:
                break
        shoot(t, "level-select")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
