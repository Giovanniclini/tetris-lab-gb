#!/usr/bin/env python3
"""High scores past a million.

    .venv/bin/python tests/test_hiscore.py

Entries are three BCD bytes - six digits - so an uncapped score has nowhere to
keep its seventh digit, and cannot be ranked against one that has one. The
seventh digits live in a parallel array; only the comparison is ours.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.emu import Tetris, sym, hATypeLevel  # noqa: E402

ROM = "build/tetrislab.gb"

wScoreBCD = 0xC0A0
wATypeHighScores = sym("wATypeHighScores")
wLabHiScoreMillions = sym("wLabHiScoreMillions")
wLabScoreMillions = sym("wLabScoreMillions")
wGameScreenBuffer = 0xC800

HISCORE_SIZEOF = 27
GS_A_TYPE_SELECTION_INIT = 0x10
LEVEL = 9

# The three dotted rows are 14 columns wide: name 0-5, a two-cell gap, score
# 8-13. The seventh digit goes in the second cell of that gap.
#
# Assert on the screen, not on wGameScreenBuffer. The original sends the names
# and the scores up as two separate blits and never copies the cells between
# them, so a row can be right in the buffer and wrong in front of the player -
# which is exactly how this shipped broken once.
ROW_VRAM = 0x9800 + 13 * 32 + 4
SEVENTH = 7


def slot(level=LEVEL):
    return wATypeHighScores + level * HISCORE_SIZEOF


def entries(t, level=LEVEL):
    """The three stored scores, as whole numbers."""
    out = []
    for i in range(3):
        b = slot(level) + i * 3
        low = (t[b] & 0x0F) + 10 * (t[b] >> 4)
        mid = (t[b + 1] & 0x0F) + 10 * (t[b + 1] >> 4)
        high = (t[b + 2] & 0x0F) + 10 * (t[b + 2] >> 4)
        m = t[wLabHiScoreMillions + level * 3 + i]
        out.append(m * 1000000 + high * 10000 + mid * 100 + low)
    return out


def bcd(n):
    """The low six digits of n, as the three bytes the game stores."""
    d = f"{n % 1000000:06d}"
    return [int(d[4:6], 16), int(d[2:4], 16), int(d[0:2], 16)]


def play_and_file(score, table=(0, 0, 0)):
    """Seed the level's three entries, finish a game worth `score`, and return
    the emulator sitting on the level select."""
    t = Tetris(ROM)
    t.start_game_at(LEVEL)
    t.tick(120)

    for i, value in enumerate(table):
        for j, byte in enumerate(bcd(value)):
            t.pb.memory[slot() + i * 3 + j] = byte
        t.pb.memory[wLabHiScoreMillions + LEVEL * 3 + i] = value // 1000000

    for j, byte in enumerate(bcd(score)):
        t.pb.memory[wScoreBCD + j] = byte
    t.pb.memory[wLabScoreMillions] = score // 1000000

    t.pb.memory[0xFFE1] = GS_A_TYPE_SELECTION_INIT   # hGameState: the game ended
    t.tick(120)
    return t


def test_a_seven_digit_score_is_filed_whole():
    with play_and_file(1000350) as t:
        assert entries(t)[0] == 1000350, f"filed as {entries(t)[0]}"


def test_a_million_beats_six_digits():
    """The original compares three bytes, so 1 000 050 stored as 000050 would
    lose to 999 999. Ranking has to see the seventh digit."""
    with play_and_file(1000050, table=(999999, 500000, 0)) as t:
        assert entries(t) == [1000050, 999999, 500000], entries(t)


def test_six_digits_cannot_beat_a_million():
    """And the same mistake in reverse."""
    with play_and_file(999999, table=(1000050, 500000, 0)) as t:
        assert entries(t) == [1000050, 999999, 500000], entries(t)


def test_the_seventh_digits_shift_with_their_entries():
    with play_and_file(2000000, table=(3000000, 1000000, 500000)) as t:
        assert entries(t) == [3000000, 2000000, 1000000], entries(t)


def test_a_score_that_does_not_place_is_left_alone():
    with play_and_file(400, table=(3000000, 1000000, 500000)) as t:
        assert entries(t) == [3000000, 1000000, 500000], entries(t)


def test_the_seventh_digit_is_shown_while_the_name_is_typed():
    """Placing sends you straight to name entry, which shows the score you just
    got. The original blanks leading zeros, so 1 000 350 would read as "350"."""
    with play_and_file(1000350) as t:
        assert t.state == 0x15, f"expected name entry, got ${t.state:02X}"
        shown = [t[ROW_VRAM + SEVENTH + i] for i in range(7)]
        assert shown == [1, 0, 0, 0, 3, 5, 0], shown


def test_the_seventh_digit_survives_onto_the_level_select():
    """The table is drawn again once the name is in."""
    with play_and_file(1000350) as t:
        t.press("start")                         # accept the name
        t.tick(30)
        assert t.state == 0x11, f"expected the level select, got ${t.state:02X}"
        shown = [t[ROW_VRAM + SEVENTH + i] for i in range(7)]
        assert shown == [1, 0, 0, 0, 3, 5, 0], shown


def test_a_six_digit_entry_still_reads_as_the_original_drew_it():
    """Rows under a million are the original's to draw - we must not touch
    them, or the leading-zero blanking it does would be undone."""
    with play_and_file(400) as t:
        row = [t[ROW_VRAM + i] for i in range(14)]
        assert row[SEVENTH] == 0x2F, f"column 7 should be blank, got ${row[SEVENTH]:02X}"
        assert row[11:14] == [4, 0, 0], f"the score itself moved: {row}"


def test_a_trainer_gets_the_uncap_without_asking_for_it():
    """The uncap sits on the shared score path, not on any mode, so a trainer
    inherits it by launching as an A-type game and does nothing else.

    The carry hooks AddScoreValueDEontoBaseScoreHL, which every score add goes
    through, and keys on the address wScoreBCD+2 rather than the game type. The
    display and the filing gate on hGameType, which trainers set to A-type. If a
    future trainer ever has to register itself with the uncap, this test is
    where that shows up.
    """
    sys.path.insert(0, str(ROOT / "tests"))
    from test_labmenu import to_menu_row

    MODE_TETRIS, MODE_TRANSITION = 0, 3
    results = {}
    for name, mode in (("TETRIS", MODE_TETRIS), ("TRANSITION", MODE_TRANSITION)):
        with Tetris(ROM) as t:
            to_menu_row(t, mode)
            t.press("start")
            t.run_until_state(0x11)              # every mode goes via the level select
            t.tick(10)
            t.press("start")
            t.run_until_state(0x00)
            t.tick(150)
            for i, byte in enumerate(bcd(257)):
                t.pb.memory[wScoreBCD + i] = byte
            t.pb.memory[wLabScoreMillions] = 1   # 1 000 257
            t.tick(60)
            level = t[hATypeLevel]
            panel = [t[0x9800 + 3 * 32 + c] for c in range(13, 20)]
            t.pb.memory[0xFFE1] = GS_A_TYPE_SELECTION_INIT
            t.tick(120)
            results[name] = (panel, entries(t, level)[0],
                             [t[ROW_VRAM + SEVENTH + i] for i in range(7)])

    assert results["TRANSITION"] == results["TETRIS"], (
        f"the trainer differs from a plain game:\n"
        f"  TETRIS     {results['TETRIS']}\n"
        f"  TRANSITION {results['TRANSITION']}"
    )
    panel, filed, shown = results["TRANSITION"]
    assert panel == [1, 0, 0, 0, 2, 5, 7], panel
    assert filed == 1000257, filed
    assert shown == [1, 0, 0, 0, 2, 5, 7], shown


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
