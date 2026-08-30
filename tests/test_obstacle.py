#!/usr/bin/env python3
"""OBSTACLE puts one column against one wall and deals nothing but bars.

    .venv/bin/python tests/test_obstacle.py

The value is TetrisGYM's (src/modes/qtap.asm): 1-$10 is the left wall that many
rows tall, $11-$20 the right, so a number means the same shape on both ROMs.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.emu import (Tetris, sym, hATypeLevel, GS_IN_GAME_MAIN,   # noqa: E402
                       GS_A_TYPE_SELECTION_MAIN)

ROM = "build/tetrislab.gb"
BUF, SCRN, W = 0xC800, 0x9800, 32
BLOCK = 0x87
ROWS, COLS = 18, 10

# The piece being played: wSpriteSpecs + SPR_SPEC_SpecIdx. Spec indexes are
# piece * 4 + rotation, and $08-$0b are the I - the four-tile run at
# SpriteTiles_08.
wCurrPieceSpec, PIECE, PIECE_I = 0xC203, 0xFC, 0x08

hPieceFallingState = 0xFF98

wLabMode, wLabObstacle = sym("wLabMode"), sym("wLabObstacle")
wLabHzValue = sym("wLabHzValue")
wLabObstacleBars = sym("wLabObstacleBars")
wScoreBCD = 0xC0A0

# The SCORE box: row 1 is its label, row 3 its digits. Columns 13 and 19 of row
# 1 are the box's own sides.
LABEL_ROW = 0x9800 + 1 * 32
VALUE_ROW = 0x9800 + 3 * 32
LINES_ROW = 0x9800 + 10 * 32
PAUSE_MAP = 0x0400              # _SCRN1 - _SCRN0
FONT = {**{i: str(i) for i in range(10)},
        **{0x0A + i: chr(ord("A") + i) for i in range(26)},
        0x24: ".", 0x25: "-", 0x2F: " "}
MODE_TETRIS, MODE_OBSTACLE = 0, 4
OBSTACLE_HEIGHT_MAX = 14        # four rows of headroom for a standing bar
OBSTACLE_RIGHT = 0x11
OBSTACLE_MAX = OBSTACLE_RIGHT + OBSTACLE_HEIGHT_MAX - 1     # $1E

# Every value the menu offers, in the order stepping right visits them: the two
# heights per side that no bar can cross are not among them.
SELECTABLE = [0] + list(range(1, OBSTACLE_HEIGHT_MAX + 1)) + \
             list(range(OBSTACLE_RIGHT, OBSTACLE_MAX + 1))


def to_row(t, row):
    t.to_menu()
    for _ in range(row):
        t.press("down")


def start(value, level=9, ticks=90):
    """A game running, with OBSTACLE set to `value`."""
    t = Tetris(ROM)
    to_row(t, MODE_OBSTACLE)
    t.pb.memory[wLabObstacle] = value
    t.press("start")
    t.run_until_state(GS_A_TYPE_SELECTION_MAIN)
    t.tick(20)
    t.pb.memory[hATypeLevel] = level
    t.press("start")
    t.run_until_state(GS_IN_GAME_MAIN)
    t.tick(ticks)
    return t


def board(t, base=SCRN):
    return ["".join("#" if t[base + r * W + 2 + c] == BLOCK else "."
                    for c in range(COLS))
            for r in range(ROWS)]


def want(value):
    """The board TetrisGYM's advanceGameTap draws for this value.

    Its $BF and $C6 are playfield indexes 191 and 198 on a 10-wide field, so
    the columns are 1 and 8 - one in from each wall, which is what leaves the
    well the bar has to be tapped into.
    """
    if value == 0:
        return ["." * COLS] * ROWS
    col, height = (1, value) if value < OBSTACLE_RIGHT else (8, value - 0x10)
    rows = ["." * COLS] * (ROWS - height)
    rows += ["." * col + "#" + "." * (COLS - col - 1)] * height
    return rows


def test_every_value_means_what_it_means_in_tetrisgym():
    for value in SELECTABLE:
        with start(value) as t:
            got = board(t)
            assert got == want(value), (
                f"${value:02X}:\n  want {want(value)}\n  got  {got}"
            )


def test_the_screen_and_the_collision_map_agree():
    """The buffer is what the piece collides against and the screen is what you
    aim by. A column drawn in one and not the other is a wall you cannot see or
    a wall that is not there."""
    for value in (0x01, 0x07, 0x0E, 0x11, 0x18, 0x1E):
        with start(value) as t:
            assert board(t, BUF) == board(t, SCRN), f"${value:02X} disagrees"


def test_every_piece_is_a_bar():
    """TetrisGYM sends MODE_TAP to pickTetriminoLongbar. Without it the drill is
    not one: the tap only has to be fast for the piece that has to reach the
    wall standing up."""
    with start(0x07, ticks=0) as t:
        seen = set()
        for _ in range(3000):
            t.tick(1)
            seen.add(t[wCurrPieceSpec] & PIECE)
        assert seen == {PIECE_I}, f"expected only the I, saw {sorted(seen)}"


def test_the_board_is_rebuilt_for_every_piece():
    """A botched tap is wiped, not stacked on - advanceGameTap clears the
    playfield each piece. Which is also the only thing keeping the drill going:
    the column would be buried inside a dozen pieces otherwise."""
    with start(0x05, ticks=0) as t:
        pieces, prev = 0, 0
        for _ in range(3000):
            t.tick(1)
            state = t[hPieceFallingState]
            if prev and not state:
                pieces += 1
            prev = state
        assert pieces >= 3, f"only {pieces} pieces landed - nothing was rebuilt"
        assert board(t) == want(0x05), f"the stack survived:\n  {board(t)}"


def test_the_preview_survives_an_instant_restart():
    """Reported by Giovanni: after A+B+Select+Start the box showed a piece the
    game was never going to deal, and pressing Select twice cleared it.

    The preview is OAM, written once per piece by the generator rather than
    rebuilt from the spec each frame the way the falling piece is. Setting the
    spec on the first frame of a game therefore leaves the last sprite in the
    box - and on a restart the last sprite is whatever the init happened to
    deal on its way through.

    Asserted against a fresh start rather than against the I's tile numbers:
    what has to hold is that a restart looks like a start.
    """
    OAM_PREVIEW = 0xFE00 + 8 * 4        # Copy2ndSpriteSpecToSprite8 writes here

    def preview(t):
        return [t[OAM_PREVIEW + i * 4 + 2] for i in range(4)]

    with start(0x05, ticks=60) as t:
        fresh = preview(t)
        t.tick(600)                     # a few pieces, so the box is the game's
        assert preview(t) == fresh, "the preview drifted during normal play"

        for b in ("a", "b", "select", "start"):
            t.pb.button_press(b)
        t.tick(4)
        for b in ("a", "b", "select", "start"):
            t.pb.button_release(b)
        t.run_until_state(GS_IN_GAME_MAIN)
        t.tick(60)

        assert preview(t) == fresh, (
            f"after a restart the box shows {[hex(v) for v in preview(t)]}, "
            f"not the bar {[hex(v) for v in fresh]}"
        )


def bars(t):
    return t[wLabObstacleBars] | (t[wLabObstacleBars + 1] << 8)


def text(t, base, first=13, last=20):
    return "".join(FONT.get(t[base + c], "?") for c in range(first, last))


def tap(t, period, count=8, button="left"):
    """`count` taps, one every `period` frames. A press needs a released frame
    in front of it to read as a fresh one, so period 2 is as fast as a Game Boy
    can be tapped and 30 Hz is the ceiling."""
    for _ in range(count):
        t.pb.button_press(button)
        t.tick(1)
        t.pb.button_release(button)
        t.tick(period - 1)


def test_the_score_box_shows_the_tap_rate():
    """Nothing scores in this drill - no line ever clears - so the panel is free
    for the number the drill is actually about."""
    with start(0x05, ticks=30) as t:
        assert "HZ" in text(t, LABEL_ROW), text(t, LABEL_ROW)
        assert "SCORE" not in text(t, LABEL_ROW), text(t, LABEL_ROW)
        assert text(t, VALUE_ROW) == "   0.00", text(t, VALUE_ROW)


def test_the_rate_is_the_formula_tetrisgym_uses():
    """hz = 60.098 * (taps - 1) / (frames - 1), which is HydrantDude's. Checked
    against the reading rather than the stored value, because the two decimals
    are the whole point of computing it in hundredths."""
    for period, want in ((2, "  30.05"), (4, "  15.02"),
                         (6, "  10.01"), (10, "   6.01")):
        expected = round(60.098 / period, 2)
        assert abs(float(want) - expected) < 0.02, (period, want, expected)
        with start(0x05, ticks=30) as t:
            tap(t, period)
            assert text(t, VALUE_ROW) == want, (
                f"a tap every {period} frames read {text(t, VALUE_ROW)}, "
                f"wanted {want}"
            )


def test_a_direction_change_starts_a_new_window():
    """TetrisGYM restarts on a change of direction, and so does a stop of more
    than sixteen frames. Tapping is one direction; alternating is not tapping,
    and averaging the two would report a rate nobody achieved."""
    with start(0x05, ticks=30) as t:
        tap(t, 4)
        rate = text(t, VALUE_ROW)
        assert rate == "  15.02", rate

        tap(t, 4, count=1, button="right")
        assert t[sym("wLabHzTaps")] == 1, "the other direction should restart"
        assert text(t, VALUE_ROW) == rate, "and leave the last reading up"


def test_the_rate_is_on_the_pause_map_too():
    """The pause screen swaps the maps over, so a panel written to one only is
    blank for as long as the game is paused."""
    with start(0x05, ticks=30) as t:
        tap(t, 4)
        assert text(t, VALUE_ROW + PAUSE_MAP) == text(t, VALUE_ROW)
        assert "HZ" in text(t, LABEL_ROW + PAUSE_MAP)


def test_the_rate_falls_to_zero_when_you_stop():
    """The rate you are tapping at, not the best you managed. Leaving the last
    reading up reads as the first, and it is the one number on screen."""
    with start(0x05, ticks=30) as t:
        tap(t, 4)
        assert text(t, VALUE_ROW) == "  15.02", text(t, VALUE_ROW)
        t.tick(20)                      # longer than the sixteen-frame window
        assert text(t, VALUE_ROW) == "   0.00", text(t, VALUE_ROW)


def test_the_lines_box_counts_bars():
    """Nothing completes a line here, so that panel is free too - and bars down
    is the length of the drill, which is what it should be counting.

    Drawn where and how the original draws its own line count: row 10, column
    14, four digits with the leading zeros blanked."""
    with start(0x05, ticks=30) as t:
        assert text(t, LINES_ROW) == "?   0 ?", text(t, LINES_ROW)
        t.tick(1500)
        landed = bars(t)
        assert landed > 3, f"only {landed} bars landed in 1500 frames"
        want = f"?{landed:>4} ?"
        assert text(t, LINES_ROW) == want, (
            f"{bars} bars read {text(t, LINES_ROW)}, wanted {want}"
        )


def test_pushing_down_works_and_scores_nothing():
    """Holding Down is a fair way to end an attempt you have already lost, so it
    still drops the piece. The point it earns is not fair: it changes the score,
    and a score change repaints the box the rate is in.

    The count of held frames is cleared every frame, which is what the original
    does itself once it has paid out - so the add is skipped, or reached with a
    count of one and pays zero. Either way the box has to survive it, and this
    taps all the way through a hundred landings to say that it does.
    """
    def drill(push):
        """Tap Left on one frame in four, and push on the next.

        Down gets its own frame because the original wants it alone ($209E),
        and it is re-pressed rather than held because a press only pushes the
        piece it was fresh for ($2077) - leaning on it through a landing does
        nothing, which is the original's rule and not ours.
        """
        with start(0x05, ticks=30) as t:
            seen = set()
            for _ in range(1500):
                t.pb.button_press("left")
                t.tick(1)
                t.pb.button_release("left")
                seen.add(text(t, VALUE_ROW))
                if push:
                    t.pb.button_press("down")
                    t.tick(1)
                    t.pb.button_release("down")
                    seen.add(text(t, VALUE_ROW))
                # Every frame, not every fourth: the redraw this is watching for
                # would last one frame and a coarser sample would walk past it.
                for _ in range(2):
                    t.tick(1)
                    seen.add(text(t, VALUE_ROW))
            return bars(t), seen, [t[wScoreBCD + i] for i in range(3)]

    fell, _, _ = drill(False)
    pushed, seen, score = drill(True)

    assert pushed > fell, (
        f"Down is not dropping the piece: {pushed} bars pushed against {fell} "
        f"left to fall"
    )
    assert all(v[4] == "." for v in seen), (
        f"the score painted over the rate: {sorted(v for v in seen if v[4] != '.')}"
    )
    assert score == [0, 0, 0], f"drop points landed on the score: {score}"


def test_the_bar_can_reach_the_well_at_every_selectable_height():
    """Reported by Tolstoj: "The bars can go higher than the spawning height,
    which is not ideal."

    A standing bar is four rows, so it can only cross the column if the column's
    top is at row 4 or below. TetrisGYM's sixteen leaves exactly those four rows
    on a 20-row field; ours is 18 rows, so the same rule is fourteen. At fifteen
    the bar stops two columns short of the well and the drill cannot be finished
    at all - which is what this walks, height by height, rather than trusting
    the arithmetic.

    Measured as how far left a standing bar gets, because the board is rebuilt
    the moment it lands and a landed piece is gone before it can be read.
    """
    X = 0xC202                      # wSpriteSpecs[0].BaseXOffset
    WELL = 31                       # against the left wall

    def leftmost(value):
        with start(value, level=0, ticks=20) as t:
            t.press("a")            # stand the bar up
            t.hold("left")
            lo = t[X]
            for _ in range(600):
                t.tick(1)
                lo = min(lo, t[X])
                if t[hPieceFallingState]:
                    break
            t.release("left")
            return lo

    # Taken off the menu, not from the constant above: "every height the drill
    # offers is playable" is the claim, and a test that asks its own idea of the
    # range would still pass if the ROM's range grew.
    with Tetris(ROM) as t:
        to_row(t, MODE_OBSTACLE)
        offered = {t[wLabObstacle]}
        for _ in range(80):
            t.press("right")
            offered.add(t[wLabObstacle])

    for value in sorted(v for v in offered if 0 < v < OBSTACLE_RIGHT):
        got = leftmost(value)
        assert got == WELL, (
            f"height {value}: the standing bar stopped at X {got}, not {WELL} - "
            f"the column is too tall to cross"
        )


def test_the_heights_no_bar_can_cross_are_not_offered():
    """The two per side that fail the test above. Asserted against the menu
    rather than against the drawing code: the value is the thing a player picks,
    and a shape that cannot be played should not be reachable."""
    with Tetris(ROM) as t:
        to_row(t, MODE_OBSTACLE)
        seen = {t[wLabObstacle]}
        for _ in range(80):
            t.press("right")
            seen.add(t[wLabObstacle])
        for _ in range(80):
            t.press("left")
            seen.add(t[wLabObstacle])
        unplayable = {0x0F, 0x10, 0x1F, 0x20}
        assert not (seen & unplayable), (
            f"the menu reaches {sorted(hex(v) for v in seen & unplayable)}"
        )


def test_the_row_counts_the_selectable_values_and_wraps():
    """TetrisGYM's own limit is $20 (MENUSIZES); ours stops at $1E because the
    last two heights per side cannot be played on an 18-row field. It shows in
    one cell because the font runs 0-9 then A-Z from $00, so the tile is the
    value - which is how TetrisGYM shows its range too."""
    with Tetris(ROM) as t:
        to_row(t, MODE_OBSTACLE)
        seen = [t[wLabObstacle]]
        for _ in range(len(SELECTABLE)):
            t.press("right")
            seen.append(t[wLabObstacle])
        assert seen == SELECTABLE + [0], [hex(v) for v in seen]
        t.press("left")
        assert t[wLabObstacle] == OBSTACLE_MAX, "Left from 0 should wrap to $1E"

        # and back down over the gap, which is a separate branch
        t.pb.memory[wLabObstacle] = OBSTACLE_RIGHT
        t.press("left")
        assert t[wLabObstacle] == OBSTACLE_HEIGHT_MAX, (
            f"left from the shortest right wall should reach the tallest left, "
            f"got ${t[wLabObstacle]:02X}"
        )


def test_it_stays_in_its_own_mode():
    """The bar forcing writes hHiddenLoadedPiece, which every mode's generator
    reads. Leaking it would turn TETRIS into a bar drill."""
    with Tetris(ROM) as t:
        to_row(t, MODE_OBSTACLE)
        t.pb.memory[wLabObstacle] = 0x08
        for _ in range(MODE_OBSTACLE):
            t.press("up")
        assert t[wLabMode] == MODE_TETRIS
        t.press("start")
        t.run_until_state(GS_A_TYPE_SELECTION_MAIN)
        t.tick(20)
        t.pb.memory[hATypeLevel] = 9
        t.press("start")
        t.run_until_state(GS_IN_GAME_MAIN)
        seen = set()
        for _ in range(2000):
            t.tick(1)
            seen.add(t[wCurrPieceSpec] & PIECE)
        assert len(seen) > 1, f"TETRIS dealt only {seen}"
        assert board(t, BUF) != want(0x08), "TETRIS drew OBSTACLE's column"


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
