#!/usr/bin/env python3
"""The Lab menu, and the transition trainer it launches.

    .venv/bin/python tests/test_labmenu.py

The menu replaces the original A-TYPE/B-TYPE screen. See docs/decisions/0007.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.emu import (Tetris, sym, hATypeLevel,  # noqa: E402
                       hNumLinesCompletedBCD, GS_IN_GAME_MAIN)

ROM = "build/tetrislab.gb"

GS_GAME_TYPE_MAIN = 0x07      # the menu lives on the title screen's state
GS_A_TYPE_SELECTION_MAIN = 0x11
GS_B_TYPE_SELECTION_MAIN = 0x13

hGameType = 0xFFC0
hMusicType = 0xFFC1
hATypeLinesThreshold = 0xFFA9              # the live level
LINES_LO, LINES_HI = hNumLinesCompletedBCD, hNumLinesCompletedBCD + 1

GAME_TYPE_A, GAME_TYPE_B = 0x37, 0x77
MUSIC_A, MUSIC_OFF = 0x1C, 0x1F

MODE_TETRIS, MODE_BTYPE, MODE_2PLAYER = 0, 1, 2
MODE_TRANSITION, MODE_SEED, MODE_MUSIC = 3, 4, 5

wLabMode = sym("wLabMode")

TILE_BLANK = 0x2F


def text(t, row, cols=range(20)):
    """Read a tilemap row back as text. The font puts 0-9 at $00 and A-Z at $0A."""
    out = ""
    for c in cols:
        v = t[0x9800 + row * 32 + c]
        if v == TILE_BLANK:
            out += " "
        elif v <= 0x09:
            out += chr(ord("0") + v)
        elif 0x0A <= v <= 0x23:
            out += chr(ord("A") + v - 0x0A)
        elif v == 0x25:
            out += "-"
        elif v == 0x26:
            out += "*"
        else:
            out += "?"
    return out.rstrip()


def to_menu(t):
    t.to_menu()
    return t


def to_menu_row(t, row):
    to_menu(t)
    return goto_row(t, row)


def goto_row(t, row):
    """Move the cursor to a row from wherever it currently is."""
    for _ in range(MODE_MUSIC + 1):
        if t[wLabMode] == row:
            return t
        t.press("down" if t[wLabMode] < row else "up")
    raise AssertionError(f"stuck on row {t[wLabMode]} heading for {row}")


def test_boot_reaches_the_title_without_the_copyright_wait():
    """The copyright screen used to hold the boot for 8.5 seconds. $24 still
    runs - the tile data and demo pieces come from it - only the timer is cut."""
    with Tetris(ROM) as t:
        for frames in range(400):
            t.pb.tick()
            if t.state == 0x07:                # GS_TITLE_SCREEN_MAIN
                break
        else:
            raise AssertionError("never reached the title screen")
        assert frames < 200, f"took {frames} frames ({frames / 59.7:.1f}s) to boot"


# The parts of GameState06_TitleScreenInit ($03AE) the Lab menu's init has to do
# itself, and where they are in the stock ROM. Everything else that init does is
# drawing the title, which the menu replaces.
TRANSCRIBED_FROM_06 = [
    ("the HRAM clears", 0x03B1, 0x03C7),
    ("the screen buffer clear", 0x03CB, 0x03D5),
    ("the walls and the floor", 0x03D6, 0x03EC),
]


def test_the_title_init_is_transcribed_not_rewritten():
    """The menu's init replaces the title screen's, so it has to redo the parts
    of it that are not about drawing - and get them exactly right.

    The floor is the one that bites: the falling piece collides against
    wGameScreenBuffer, so without it a piece falls past the bottom for ever and
    the game hangs somewhere else entirely. Asserting the bytes rather than the
    behaviour is what stops that drifting again."""
    stock = (ROOT / "build/tetris.gb").read_bytes()
    lab = (ROOT / ROM).read_bytes()

    where = []
    for name, lo, hi in TRANSCRIBED_FROM_06:
        seq = stock[lo:hi + 1]
        at = lab.find(seq, 0x8000)
        assert at >= 0, f"{name} (${lo:04X}-${hi:04X}) is not in the Lab banks verbatim"
        where.append((name, at, len(seq)))

    # ... and in order, with nothing spliced between them.
    for (name, at, size), (next_name, next_at, _) in zip(where, where[1:]):
        assert at + size == next_at, (
            f"{next_name} does not directly follow {name} "
            f"(${at + size:04X} vs ${next_at:04X})"
        )


def test_the_menu_starts_its_music():
    """The screens this menu replaced each started a song. Without one the menu
    is silent until you nudge the MUSIC row, which is how the omission showed."""
    with Tetris(ROM) as t:
        songs = []
        # $1521: `ld [wSongToStart], a` inside PlaySongBasedOnMusicTypeChosen
        t.pb.hook_register(0, 0x1521, lambda _: songs.append(t.pb.register_file.A), None)
        t.run_until_state(GS_GAME_TYPE_MAIN)
        t.tick(20)
        assert songs, "the menu asked for no music at all"

        songs.clear()
        t.press("start")
        t.run_until_state(GS_A_TYPE_SELECTION_MAIN)
        t.tick(20)
        songs.clear()
        t.press("b")
        t.tick(40)
        assert songs, "coming back to the menu left it silent"


def test_settings_survive_a_round_trip_through_a_game():
    """A trainer keeps what you set up - that is the point of it. The original
    cleared the level whenever you passed through the title screen; the menu
    that replaced it deliberately does not."""
    with Tetris(ROM) as t:
        to_menu_row(t, MODE_TRANSITION)
        for _ in range(7):
            t.press("right")                   # transition level 7

        goto_row(t, MODE_SEED)
        t.press("a")
        for _ in range(0xA):
            t.press("up")                      # first digit -> A
        t.press("a")

        level, seed = t[sym("wLabDrillScore")], t[sym("wLabSeedHi")]
        assert level == 7 and seed, f"setup failed: level {level}, seed hi ${seed:02X}"

        goto_row(t, MODE_TETRIS)
        t.press("start")
        t.run_until_state(GS_A_TYPE_SELECTION_MAIN)
        t.tick(20)
        t.press("b")
        t.tick(40)

        assert t[sym("wLabDrillScore")] == level, "the transition value was reset"
        assert t[sym("wLabSeedHi")] == seed, "the seed was reset"


def test_the_original_title_screen_never_appears():
    """Not on boot, and not on the way back from a level select. $06 draws the
    menu itself rather than the title, so there is no frame to catch."""
    def title_frames(t, limit):
        n = 0
        for _ in range(limit):
            t.pb.tick()
            row = text(t, 9).replace(" ", "")
            if "PLAYER" in row:
                n += 1
        return n

    with Tetris(ROM) as t:
        assert title_frames(t, 160) == 0, "the 1P/2P title flashed during boot"
        t.run_until_state(GS_GAME_TYPE_MAIN)
        t.tick(20)
        t.press("start")
        t.run_until_state(GS_A_TYPE_SELECTION_MAIN)
        t.tick(20)
        t.press("b")
        assert title_frames(t, 90) == 0, "a screen flashed on the way back"


def test_gameplay_survives_the_replaced_title_init():
    """The falling piece collides against wGameScreenBuffer, and it is the
    title init that puts the walls and floor there. Replacing that init without
    them makes a piece fall past the bottom for ever."""
    with Tetris(ROM) as t:
        t.start_game_at(22)                    # M tops out unaided
        for frames in range(2000):
            t.pb.tick()
            if t.state == 0x04:                # GS_LEVEL_ENDED_MAIN
                break
        else:
            raise AssertionError("no game over: the piece never landed")
        assert frames < 600, f"took {frames} frames to top out at M"


def test_the_level_select_renders_like_the_stock_rom():
    """The menu tileset comes from bank 1, so the Lab has to far-call for it -
    without that the level select drew the title screen's tiles as garbage."""
    with Tetris(ROM) as lab, Tetris("build/tetris.gb") as stock:
        lab.to_level_select(); lab.tick(30)
        stock.to_level_select(); stock.tick(30)
        differing = [(r, c) for r in range(18) for c in range(20)
                     if lab[0x9800 + r * 32 + c] != stock[0x9800 + r * 32 + c]]
        assert len(differing) <= 1, (
            f"{len(differing)} cells differ from the stock level select: {differing[:8]}"
        )


def test_b_from_the_level_select_returns_to_the_menu():
    """B goes to $08, which would draw the A-TYPE/B-TYPE screen the menu
    replaced."""
    with Tetris(ROM) as t:
        t.to_level_select()
        t.press("b")
        t.tick(60)
        assert t.state == GS_GAME_TYPE_MAIN, f"landed on state ${t.state:02X}"


def test_the_menu_replaces_the_game_type_screen():
    with Tetris(ROM) as t:
        to_menu(t)
        rows = [text(t, r) for r in range(18)]
        joined = "\n".join(rows)
        for want in ("TETRIS LAB", "TETRIS", "B-TYPE", "2 PLAYER",
                     "TRANSITION", "SEED", "MUSIC"):
            assert want in joined, f"{want!r} missing from the menu:\n{joined}"
        assert "1PLAYER" not in joined, "the original title screen is still showing"


def test_the_cursor_moves_and_wraps():
    with Tetris(ROM) as t:
        to_menu(t)
        assert t[wLabMode] == MODE_TETRIS, "should open on the first row"
        t.press("up")
        assert t[wLabMode] == MODE_MUSIC, "Up from the first row should wrap"
        t.press("down")
        assert t[wLabMode] == MODE_TETRIS, "Down from the last row should wrap"


def test_tetris_launches_the_a_type_level_select():
    with Tetris(ROM) as t:
        to_menu_row(t, MODE_TETRIS)
        t.press("start")
        t.run_until_state(GS_A_TYPE_SELECTION_MAIN)
        assert t[hGameType] == GAME_TYPE_A, f"game type is ${t[hGameType]:02X}"


def test_b_type_launches_the_b_type_level_select():
    with Tetris(ROM) as t:
        to_menu_row(t, MODE_BTYPE)
        t.press("start")
        t.run_until_state(GS_B_TYPE_SELECTION_MAIN)
        assert t[hGameType] == GAME_TYPE_B, f"game type is ${t[hGameType]:02X}"


def test_b_type_is_untouched_by_the_score_uncap():
    """The uncap follows the original's own structure rather than inventing a
    limit: the original displays a score in A-type only ($243F), so the seventh
    digit does too. B-type is 25 lines and tops out near 100 000, so it has no
    seventh digit to show and no cell of ours to keep clear."""
    with Tetris(ROM) as t:
        to_menu_row(t, MODE_BTYPE)
        t.press("start")
        t.run_until_state(GS_B_TYPE_SELECTION_MAIN)
        t.press("start")
        t.run_until_state(0x00)
        t.tick(120)
        t.pb.memory[sym("wLabScoreMillions")] = 9     # as if it had carried
        t.tick(60)
        for cell in (13, 19):
            tile = t[0x9800 + 3 * 32 + cell]
            assert tile > 9, (
                f"column {cell} shows digit {tile} in B-type, where the original "
                f"draws no score at all"
            )


def test_the_seed_row_opens_its_digits_with_a():
    with Tetris(ROM) as t:
        to_menu_row(t, MODE_SEED)
        idle = t[sym("wLabSeedDigit")]
        assert idle == 0xFF, f"should start closed, got {idle}"
        t.press("a")
        assert t[sym("wLabSeedDigit")] == 0, "A should open the first digit"
        t.press("right")
        assert t[sym("wLabSeedDigit")] == 1, "Right should step to the next digit"
        t.press("a")
        assert t[sym("wLabSeedDigit")] == 0xFF, "A should close the digits"
        assert t.state == GS_GAME_TYPE_MAIN, "A on a setting started something"


def test_music_is_a_setting_not_a_mode():
    """TetrisGYM splits its list at MODE_GAME_QUANTITY: rows past it configure
    the game rather than starting one. Start must do nothing here."""
    with Tetris(ROM) as t:
        to_menu_row(t, MODE_MUSIC)
        seen = []
        for _ in range(5):
            seen.append(t[hMusicType])
            t.press("right")
        assert seen == [MUSIC_A, MUSIC_A + 1, MUSIC_A + 2, MUSIC_OFF, MUSIC_A], (
            f"music should cycle A/B/C/OFF and wrap, saw {[hex(x) for x in seen]}"
        )
        t.press("start")
        t.tick(10)
        assert t.state == GS_GAME_TYPE_MAIN, (
            f"Start on a setting started something (state ${t.state:02X})"
        )


def _run_drill(t, level, value=0):
    """TRANSITION launches like every other row: the level comes from the level
    select, and the row carries the trainer's own parameter - the score you
    start on, in hundreds of thousands."""
    to_menu_row(t, MODE_TRANSITION)
    for _ in range(value):
        t.press("right")
    assert t[sym("wLabDrillScore")] == value, "the row did not take the value"
    t.press("start")
    t.run_until_state(GS_A_TYPE_SELECTION_MAIN)
    t.tick(10)
    t.pb.memory[hATypeLevel] = level     # as start_game_at does, cursor aside
    t.press("start")
    t.run_until_state(GS_IN_GAME_MAIN)
    t.tick(12)
    assert t[hATypeLevel] == level, f"started on level {t[hATypeLevel]}"
    return int(f"{t[LINES_HI]:02X}{t[LINES_LO]:02X}")   # BCD -> decimal


def _score(t):
    low = int("".join(f"{t[0xC0A0 + 2 - i]:02X}" for i in range(3)))
    return t[sym("wLabScoreMillions")] * 1000000 + low


def test_the_row_presets_the_score_in_hundreds_of_thousands():
    """TetrisGYM's Transition value is a starting score, not a level: set it to
    5 and start on 18 for a maxout trainer (src/gamemodestate/initstate.asm).

    Ten and above overflow into the seventh digit rather than writing a
    non-decimal nibble into the top BCD byte."""
    for value, want in ((0, 0), (5, 500000), (9, 900000),
                        (10, 1000000), (15, 1500000)):
        with Tetris(ROM) as t:
            _run_drill(t, 9, value)
            assert _score(t) == want, f"value {value} gave {_score(t)}"


def test_the_preset_score_is_on_screen_before_a_piece_lands():
    """The original only redraws the score when drop points land and the piece
    has finished falling ($01DB), so a preset would sit invisible until the
    first piece hit the ground. Reported by Giovanni."""
    for value, want in ((0, "......0"), (5, ".500000"), (15, "1500000")):
        with Tetris(ROM) as t:
            _run_drill(t, 9, value)
            row = "".join(
                f"{t[0x9800 + 3 * 32 + c]:x}" if t[0x9800 + 3 * 32 + c] <= 9 else "."
                for c in range(13, 20)
            )
            assert row == want, f"value {value} showed {row}, expected {want}"


def test_the_row_stops_at_f():
    """0-9 then A-F. TetrisGYM has one more, G, which turns its trainer off for
    SXTOKL compatibility - a Game Genie code that changes the NES's
    first-transition formula. The Game Boy has no such formula."""
    with Tetris(ROM) as t:
        to_menu_row(t, MODE_TRANSITION)
        for _ in range(20):
            t.press("right")
        assert t[sym("wLabDrillScore")] == 0x0F, (
            f"the row reached {t[sym('wLabDrillScore')]:#x}, should stop at $0F"
        )


def test_the_level_comes_only_from_the_level_select():
    """The row used to carry a level too, which then disagreed with the level
    select after a game over."""
    with Tetris(ROM) as t:
        _run_drill(t, 12, value=5)
        assert t[hATypeLevel] == 12


def test_transition_starts_ten_lines_short_of_the_level_up():
    """The game levels up when lines/10 exceeds the level, so a level 9 start
    transitions at 100. TetrisGYM lands you on the last ten-line boundary
    before that; here that is 90."""
    for level in (5, 9, 12, 18, 22):
        with Tetris(ROM) as t:
            got, want = _run_drill(t, level), level * 10
            assert got == want, (
                f"level {level}: transitions at {(level + 1) * 10} lines, "
                f"drill should start at {want}, got {got}"
            )
            assert t[hATypeLinesThreshold] == level, "the drill changed the level"


def test_transition_at_level_zero_preloads_nothing():
    with Tetris(ROM) as t:
        assert _run_drill(t, 0) == 0, "level 0 transitions at 10; nothing to skip"


def test_the_lines_readout_is_repainted():
    """The original only redraws the line count on a clear, so the drill has to
    paint it itself or the game shows 000 until the first one."""
    with Tetris(ROM) as t:
        _run_drill(t, 9)
        assert text(t, 10, range(14, 18)).strip() == "90", (
            f"LINES reads {text(t, 10, range(14, 18))!r}, expected 90"
        )


def test_a_plain_tetris_game_is_not_a_drill():
    with Tetris(ROM) as t:
        to_menu_row(t, MODE_TETRIS)
        t.press("start")
        t.run_until_state(GS_A_TYPE_SELECTION_MAIN)
        t.tick(6)
        t.pb.memory[hATypeLevel] = 9
        t.press("start")
        t.run_until_state(GS_IN_GAME_MAIN)
        t.tick(20)
        assert t[LINES_HI] == 0 and t[LINES_LO] == 0, "TETRIS preloaded lines"


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
