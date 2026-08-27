#!/usr/bin/env python3
"""CRUNCH narrows the playfield, TetrisGYM's way.

    .venv/bin/python tests/test_crunch.py

The value is theirs (src/modes/crunch.asm): every 4 takes a column off the
left, every 1 off the right, so a number means the same shape on both ROMs.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.emu import (Tetris, sym, GS_IN_GAME_MAIN,        # noqa: E402
                       GS_A_TYPE_SELECTION_MAIN)

ROM = "build/tetrislab.gb"
BUF, SCRN, W = 0xC800, 0x9800, 32
BLOCK, EMPTY = 0x87, 0x2F
hRowsShiftingDownState = 0xFFB2

wLabMode = sym("wLabMode")
wLabCrunch = sym("wLabCrunch")
MODE_TETRIS, MODE_CRUNCH = 0, 3


def start(value, mode=MODE_CRUNCH):
    """A game running, with CRUNCH set to `value`."""
    t = Tetris(ROM)
    t.to_menu()
    for _ in range(mode):
        t.press("down")
    t.pb.memory[wLabCrunch] = value
    t.press("start")
    t.run_until_state(GS_A_TYPE_SELECTION_MAIN)
    t.tick(20)
    t.press("start")
    t.run_until_state(GS_IN_GAME_MAIN)
    t.tick(90)
    return t


def shape(t, row, base=SCRN):
    return "".join("#" if t[base + row * W + 2 + c] == BLOCK else "."
                   for c in range(10))


# The table in the header of TetrisGYM's src/modes/crunch.asm, transcribed.
# All sixteen, because "same as TetrisGYM" is the whole claim and a sample of
# it is not the claim.
TETRISGYM = {0x0: (0, 0), 0x1: (0, 1), 0x2: (0, 2), 0x3: (0, 3),
             0x4: (1, 0), 0x5: (1, 1), 0x6: (1, 2), 0x7: (1, 3),
             0x8: (2, 0), 0x9: (2, 1), 0xA: (2, 2), 0xB: (2, 3),
             0xC: (3, 0), 0xD: (3, 1), 0xE: (3, 2), 0xF: (3, 3)}


def test_every_value_means_what_it_means_in_tetrisgym():
    for value, (left, right) in TETRISGYM.items():
        want = "#" * left + "." * (10 - left - right) + "#" * right
        with start(value) as t:
            got = shape(t, 10)
            assert got == want, (
                f"${value:X} should be {left} left {right} right "
                f"({want}), got {got}"
            )


def test_the_row_counts_the_way_their_readme_says():
    """"Every increment of 4 will decrease the width from the left. Every
    increment of 1 will decrease the width from the right until it reaches its
    maximum of 3, where it will be reset to 0."

    Which is a plain 0-F counter: the right is the low two bits, so it carries
    into the left by itself. Worth asserting rather than assuming, because that
    sentence can also be read as the right wrapping without the carry.
    """
    with Tetris(ROM) as t:
        t.to_menu()
        for _ in range(MODE_CRUNCH):
            t.press("down")
        seen = [t[wLabCrunch]]
        for _ in range(16):
            t.press("right")
            seen.append(t[wLabCrunch])
        assert seen == list(range(16)) + [0], seen
        t.press("left")
        assert t[wLabCrunch] == 0x0F, "Left from 0 should wrap to F"


def test_every_row_is_narrowed_not_just_the_visible_one():
    with start(0x0A) as t:
        for row in (0, 8, 17):
            assert shape(t, row) == "##......##", f"row {row}: {shape(t, row)}"


def test_the_columns_survive_a_line_clear():
    """A clear shifts the ten playfield columns down and clears the row left at
    the top - so the field widens back out from row 0, one clear at a time.
    TetrisGYM re-runs advanceSides for the same reason.

    Row 0 is the whole test. Every other row inherits its columns from the row
    above it, so they look right whether or not anything refills them - which is
    what this test asserted first, and it passed with the refill deleted.
    """
    with start(0x0A) as t:
        for c in range(2, 8):                       # fill the narrow gap
            t.pb.memory[BUF + 17 * W + 2 + c] = BLOCK
        seen = False
        for _ in range(900):
            t.tick(1)
            if t[hRowsShiftingDownState]:
                seen = True
        assert seen, "no line clear happened, so this proved nothing"
        t.tick(120)
        for row in (0, 1, 17):
            got = shape(t, row, BUF)
            assert got == "##......##", (
                f"row {row} lost its crunch columns after a clear: {got}"
            )


def test_crunch_does_nothing_in_other_modes():
    """It is a mode, not a modifier - the value is ignored by TETRIS."""
    with start(0x0F, mode=MODE_TETRIS) as t:
        assert t[wLabMode] == MODE_TETRIS
        assert shape(t, 10) == "..........", shape(t, 10)


TESTS = [v for k, v in sorted(globals().items()) if k.startswith("test_")]

if __name__ == "__main__":
    failures = 0
    for fn in TESTS:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
        except AssertionError as exc:
            failures += 1
            print(f"FAIL  {fn.__name__}: {exc}")
    print(f"\n{len(TESTS) - failures}/{len(TESTS)} passed")
    raise SystemExit(1 if failures else 0)
