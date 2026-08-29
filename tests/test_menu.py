#!/usr/bin/env python3
"""Level picker on the A-TYPE selection screen.

    .venv/bin/python tests/test_menu.py

The original 0-9 grid is left completely alone. The Lab adds one cell to its
right, reached by pressing Right on cell 9 - a press the original ignores.
See docs/decisions/0003.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.emu import (Tetris, sym, hATypeLevel, hIsHardMode,  # noqa: E402
                       GS_IN_GAME_MAIN, GS_A_TYPE_SELECTION_MAIN)

ROM = "build/tetrislab.gb"

wScoreBCD = 0xC0A0                              # src/original/include/wram.s
HISCORE_SIZEOF = 27                             # src/original/include/structs.s

wLabFocus = sym("wLabFocus")
wLabPickerLevel = sym("wLabPickerLevel")
PICKER_FIRST = 10        # A - the grid covers 0-9
FOCUS_GRID, FOCUS_LEVEL = 0, 1

GRID_CELLS = ([0x9800 + 6 * 32 + 5 + 2 * i for i in range(5)]
              + [0x9800 + 8 * 32 + 5 + 2 * i for i in range(5)])
GRID_TILES = [0x90 + i for i in range(10)]      # the original's digit art
PICKER_CELL = 0x9800 + 6 * 32 + 16
HEART_CELL = 0x9800 + 4 * 32 + 14
SPRITE_HIDDEN_BYTE = 0xC200

TILE_HEART, TILE_FRAME, TILE_BLANK = 0x27, 0x2C, 0x2F
MAX_LEVEL = 22

GRAVITY = [53, 49, 45, 41, 37, 33, 28, 22, 17, 11,
           10, 9, 8, 7, 6, 6, 5, 5, 4, 4, 3, 2, 1]


def open_picker(t):
    """Walk the grid to cell 9 and press Right once more."""
    t.to_level_select()
    t.tick(4)
    while t[hATypeLevel] < 9:
        t.press("right")
    t.press("right")
    assert t[wLabFocus] == FOCUS_LEVEL, "Right on cell 9 should focus the level field"
    return t


def picker_to(t, level):
    for _ in range(MAX_LEVEL + 1):
        here = t[wLabPickerLevel]
        if here == level:
            return t
        t.press("up" if here < level else "down")
    raise AssertionError(f"stuck at {t[wLabPickerLevel]} heading for {level}")


def test_the_original_grid_is_never_modified():
    """The whole point of this design: the 0-9 grid keeps its own tiles,
    cursor and movement."""
    with Tetris(ROM) as t:
        open_picker(t)
        picker_to(t, MAX_LEVEL)
        t.tick(40)
        got = [t[a] for a in GRID_CELLS]
        assert got == GRID_TILES, f"grid tiles changed: {[hex(x) for x in got]}"


def test_grid_movement_is_unchanged():
    with Tetris(ROM) as t:
        t.to_level_select()
        t.tick(4)
        for expected in (1, 2, 3, 4, 5):
            t.press("right")
            assert t[hATypeLevel] == expected
        t.press("down")
        assert t[hATypeLevel] == 5, "Down on the bottom row should do nothing"
        t.press("up")
        assert t[hATypeLevel] == 0, "Up from cell 5 should reach cell 0"


def test_picker_opens_and_closes_from_the_grid():
    """Left leaves the field from any level, not just from 0."""
    with Tetris(ROM) as t:
        open_picker(t)
        picker_to(t, 12)
        t.press("left")
        assert t[wLabFocus] == FOCUS_GRID, "focus should have returned to the grid"
        assert t[hATypeLevel] == 9, "focus should return to grid cell 9"


def test_the_level_select_says_which_mode_it_is_setting_up():
    """The layout says A-TYPE because that is what the original screen is. For
    a trainer it is the wrong word - the screen you are setting up is CRUNCH's,
    and nothing on it said so.

    The label is the same string the menu row draws, so the two cannot drift.

    Spacing is part of it: the layout sets A-TYPE off with a blank either side,
    and a name long enough to pass the right-hand one has to bring its own or it
    meets the frame's dots with nothing between.
    """
    HEADER = [0x9800 + 1 * 32 + c for c in range(2, 14)]

    def header(row):
        with Tetris(ROM) as t:
            t.to_menu()
            for _ in range(row):
                t.press("down")
            t.press("start")
            t.run_until_state(GS_A_TYPE_SELECTION_MAIN)
            t.tick(30)
            out = ""
            for a in HEADER:
                v = t[a]
                if 0x0A <= v <= 0x23:
                    out += chr(ord("A") + v - 0x0A)
                elif v == 0x25:
                    out += "-"
                elif v <= 9:
                    out += "0123456789"[v]
                else:
                    break                       # frame or blank: end of the word
            return out

    def spaced(row, word):
        """The word, with a blank on each side of it."""
        with Tetris(ROM) as t:
            t.to_menu()
            for _ in range(row):
                t.press("down")
            t.press("start")
            t.run_until_state(GS_A_TYPE_SELECTION_MAIN)
            t.tick(30)
            before = t[0x9800 + 1 * 32 + 1]
            after = t[0x9800 + 1 * 32 + 2 + len(word)]
            return before == TILE_BLANK and after == TILE_BLANK

    MODE_TETRIS, MODE_TRANSITION, MODE_CRUNCH = 0, 2, 3
    for row, word in ((MODE_TETRIS, "A-TYPE"), (MODE_TRANSITION, "TRANSITION"),
                      (MODE_CRUNCH, "CRUNCH")):
        assert header(row) == word, f"header reads {header(row)!r}, wanted {word!r}"
        assert spaced(row, word), f"{word} is not set off by a blank on both sides"


def test_picker_clamps_at_both_ends():
    """Up and Down stop at M and at A. The grid already offers 0-9, so the
    picker starts where the grid stops - a level belongs to one field or the
    other, never both. Down at A is not the way out of the field either; Left
    is, from any level.
    """
    with Tetris(ROM) as t:
        open_picker(t)
        for _ in range(30):
            t.press("up")
        assert t[wLabPickerLevel] == MAX_LEVEL, "should stop at M"
        for _ in range(30):
            t.press("down")
        assert t[wLabPickerLevel] == PICKER_FIRST, (
            f"should stop at A, got {t[wLabPickerLevel]}"
        )
        assert t[wLabFocus] == FOCUS_LEVEL, "Down at A should not leave the field"


def test_picker_cell_shows_the_level_character():
    """The font puts 0-9 at $00-$09 and A-M at $0A-$16, so the tile is simply
    the level number."""
    with Tetris(ROM) as t:
        open_picker(t)
        for level in (10, 15, 20, 21, 22):
            picker_to(t, level)
            seen = set()
            for _ in range(40):
                t.tick(1)
                seen.add(t[PICKER_CELL])
            assert level in seen, (
                f"level {level}: expected tile ${level:02X}, saw "
                f"{[hex(x) for x in seen]}"
            )


def test_picker_blinks_only_while_it_has_focus():
    with Tetris(ROM) as t:
        open_picker(t)
        picker_to(t, 12)
        seen = set()
        for _ in range(40):
            t.tick(1)
            seen.add(t[PICKER_CELL])
        assert seen == {12, TILE_BLANK}, f"expected a blink, saw {seen}"

        t.press("left")                       # back to the grid
        seen = set()
        for _ in range(40):
            t.tick(1)
            seen.add(t[PICKER_CELL])
        assert seen == {12}, f"should be steady once unfocused, saw {seen}"


def test_grid_cursor_is_hidden_while_the_picker_has_focus():
    """The cursor sprite draws the character for hATypeLevel, not what the
    picker shows, so it must not appear on screen.

    Asserted against OAM rather than the spec byte: the original copies the
    specs into OAM itself, so setting the hidden bit after that copy is not
    enough on its own.
    """
    with Tetris(ROM) as t:
        open_picker(t)
        picker_to(t, 15)
        for _ in range(40):
            t.tick(1)
            y = t[0xFE00]
            assert y == 0 or y >= 160, f"grid cursor visible on screen at Y={y}"


def test_the_level_field_swallows_up_and_down():
    """They change the level. The original reads the same presses to move the
    grid cursor, and would do so underneath us - then Left would hand focus
    back to a cell the player never chose."""
    with Tetris(ROM) as t:
        open_picker(t)
        before = t[hATypeLevel]
        for direction in ("up", "down", "up"):
            t.press(direction)
            assert t[hATypeLevel] == before, "grid cursor moved under the level field"
            assert t[wLabFocus] == FOCUS_LEVEL, "focus changed"


def test_the_level_field_is_the_only_one_left():
    """The seed moved to the Lab menu (docs/decisions/0007), so Right on the
    level field has nowhere to go and must be swallowed rather than reaching
    the original underneath."""
    with Tetris(ROM) as t:
        open_picker(t)
        before = t[hATypeLevel]
        t.press("right")
        assert t[wLabFocus] == FOCUS_LEVEL, f"focus left the level field: {t[wLabFocus]}"
        assert t[hATypeLevel] == before, "grid cursor moved under the level field"


def test_starting_from_the_picker_uses_its_level():
    for level in (10, 15, 20, 21, 22):
        with Tetris(ROM) as t:
            open_picker(t)
            picker_to(t, level)
            t.press("start")
            t.run_until_state(GS_IN_GAME_MAIN)
            assert t[hATypeLevel] == level, (
                f"expected level {level}, got {t[hATypeLevel]}"
            )
            assert t.gravity() == GRAVITY[level], (
                f"level {level}: expected {GRAVITY[level]} frames/row, "
                f"got {t.gravity()}"
            )


def test_starting_from_the_grid_still_works():
    for level in (0, 5, 9):
        with Tetris(ROM) as t:
            t.to_level_select()
            t.tick(4)
            while t[hATypeLevel] < level:
                t.press("right")
            t.press("start")
            t.run_until_state(GS_IN_GAME_MAIN)
            assert t[hATypeLevel] == level
            assert t.gravity() == GRAVITY[level]


def test_select_toggles_hearts_and_shows_an_indicator():
    with Tetris(ROM) as t:
        t.to_level_select()
        t.tick(4)
        assert t[hIsHardMode] == 0
        assert t[HEART_CELL] == TILE_FRAME

        t.press("select")
        t.tick(2)
        assert t[hIsHardMode] != 0
        assert t[HEART_CELL] == TILE_HEART

        t.press("select")
        t.tick(2)
        assert t[hIsHardMode] == 0
        assert t[HEART_CELL] == TILE_FRAME


def test_hearts_are_cleared_above_level_20():
    """min(level + 10, 20) clamps downward past level 20, which would make the
    game slower. See docs/existing-hacks.md 3.2b."""
    with Tetris(ROM) as t:
        t.to_level_select()
        t.tick(4)
        t.press("select")
        assert t[hIsHardMode] != 0
        while t[hATypeLevel] < 9:            # already on the screen; do not renavigate
            t.press("right")
        t.press("right")                     # into the level field
        assert t[wLabFocus]
        picker_to(t, 21)
        t.tick(4)
        assert t[hIsHardMode] == 0, "hearts should be cleared above level 20"
        assert t[HEART_CELL] == TILE_FRAME


def test_heart_speeds_are_unchanged_for_the_original_levels():
    for level, effective in ((0, 10), (5, 15), (9, 19)):
        with Tetris(ROM) as t:
            t.start_game_at(level, hearts=True)
            assert t.gravity() == GRAVITY[effective]


def test_the_extended_table_continues_the_original_one():
    """The original indexes wATypeHighScores + level * HISCORE_SIZEOF with no
    bound check. The Lab's slots for A-M are correct only because they sit
    exactly where that arithmetic already points."""
    base, ext = sym("wATypeHighScores"), sym("wLabATypeHighScoresExt")
    assert ext == base + 10 * HISCORE_SIZEOF, (
        f"extension at ${ext:04X}, expected ${base + 10 * HISCORE_SIZEOF:04X}"
    )


def test_a_score_is_filed_under_the_level_it_was_played_at():
    """Before the extension the index ran off the end of the ten-slot table and
    the Lab clamped it back to 9 - so a game at M filed its score under 9, and
    that is where it showed up. See docs/decisions/0006."""
    score = (0x00, 0x00, 0x11)                             # 110000, in BCD
    with Tetris(ROM) as t:
        t.start_game_at(22)                                # M tops out unaided
        for _ in range(900):
            t.tick(1)
            if t.state == 0x04:                            # GS_LEVEL_ENDED_MAIN
                break
        assert t.state == 0x04, f"never reached game over (state ${t.state:02X})"

        # M tops out too fast to score anything, so plant one. wScoreBCD holds
        # until the level select files it, which is the path under test.
        for i, v in enumerate(score):
            t.pb.memory[wScoreBCD + i] = v
        t.press("start")                                   # back to the select
        t.tick(40)

        base = sym("wATypeHighScores")
        m, nine = base + 22 * HISCORE_SIZEOF, base + 9 * HISCORE_SIZEOF
        assert tuple(t[m + i] for i in range(3)) == score, "M did not keep the score"
        assert not any(t[nine + i] for i in range(3)), "the score leaked into level 9"


def test_high_scores_follow_the_picked_level():
    """The TOP SCORE panel is driven by hATypeLevel, which the Lab keeps as the
    grid index while the level field has focus - so it used to keep showing the
    grid cursor's scores while you had M selected.

    Level 5 is reached on the grid and M in the picker, because those are the
    only places they exist: the picker offers A-M and the grid 0-9, with no
    overlap between them.
    """
    PANEL = [0x9800 + r * 32 + c for r in (13, 14, 15) for c in range(3, 17)]
    TILE_DOT = 0x60

    def plant(t, slot):
        for i, v in enumerate((0x12, 0x34, 0x56)):
            t.pb.memory[slot + i] = v
        for i in range(6):
            t.pb.memory[slot + 9 + i] = 0x0A + i

    def dots(t):
        t.tick(20)
        return sum(1 for a in PANEL if t[a] == TILE_DOT)

    with Tetris(ROM) as t:
        t.to_level_select()
        base = sym("wATypeHighScores")
        plant(t, base + 5 * HISCORE_SIZEOF)                # level 5
        plant(t, base + 22 * HISCORE_SIZEOF)               # level M

        t.press("right")
        t.press("left")                                    # force a refresh
        empty = dots(t)                                    # level 0: nothing set

        while t[hATypeLevel] < 5:
            t.press("right")
        with_score = dots(t)
        assert with_score < empty, "planted score did not show; test proves nothing"

        while t[hATypeLevel] < 9:
            t.press("right")
        t.press("right")                                   # level field, at 10
        assert dots(t) == empty, "A has no score yet; expected placeholders"

        while t[wLabPickerLevel] < 22:
            t.press("up")
        assert dots(t) == with_score, (
            "M has its own slot and the panel should follow the field onto it"
        )


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
