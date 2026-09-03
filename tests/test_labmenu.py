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

GS_GAME_TYPE_MAIN = 0x0e      # the menu lives on the game type screen's states
GS_A_TYPE_SELECTION_MAIN = 0x11
GS_B_TYPE_SELECTION_MAIN = 0x13

hGameType = 0xFFC0
hMusicType = 0xFFC1
hATypeLinesThreshold = 0xFFA9              # the live level
LINES_LO, LINES_HI = hNumLinesCompletedBCD, hNumLinesCompletedBCD + 1

GAME_TYPE_A, GAME_TYPE_B = 0x37, 0x77
MUSIC_A, MUSIC_OFF = 0x1C, 0x1F

MODE_TETRIS, MODE_BTYPE, MODE_TRANSITION = 0, 1, 2
MODE_CRUNCH, MODE_OBSTACLE = 3, 4

MODE_SEED, MODE_MUSIC = 5, 6
# Which map row each mode's entry is drawn on, from Tolstoj's layout.
MENU_MAP_ROWS = {MODE_MUSIC: 8, MODE_TETRIS: 14, MODE_BTYPE: 15,
                 MODE_SEED: 19, MODE_TRANSITION: 24, MODE_CRUNCH: 25,
                 MODE_OBSTACLE: 26}


wLabMode = sym("wLabMode")
wLabMenuRow = sym("wLabMenuRow")
hIs2Player = 0xFFC5

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


def goto_row(t, mode):
    """Move the cursor to the row that selects `mode`.

    Down only, and wrapping: the list is Tolstoj's layout, so its row order is
    his and has nothing to do with the mode numbering - "is my mode above or
    below yours" is not a question the numbers can answer any more.
    """
    for _ in range(20):
        if t[wLabMode] == mode:
            return t
        t.press("down")
    raise AssertionError(f"never reached mode {mode} from the menu")


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
        t.to_menu()
        assert songs, "the menu asked for no music at all"

        songs.clear()
        t.to_mode(MODE_TETRIS)
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


def test_the_title_screen_offers_both_player_counts():
    """The screen the menu used to stand on, with Tolstoj's artwork on it."""
    with Tetris(ROM) as t:
        t.to_title()
        t.tick(20)
        rows = "\n".join(text(t, r) for r in range(18))
        assert rows.count("PLAYER") == 2, f"not the title screen:\n{rows}"
        assert t[0x9800 + 15 * 32] == 0x9C, "no cursor beside 1 PLAYER"


def test_screens_downstream_of_the_title_get_the_menu_tileset():
    """The title screen lays its own tiles over VRAM. Everything after it - the
    menu, the level select, the game - reads Gfx_MenuScreens from $30 up, so
    each has to reload the tileset on the way in.

    This is the trap ADR 0007 records and it has now been walked into twice: the
    tilemap is identical either way, so the screen is laid out correctly and
    drawn in the wrong alphabet. Nothing about the layout catches it; only the
    tile data does.
    """
    rom = (ROOT / "build" / "tetrislab.gb").read_bytes()
    syms = {}
    for line in (ROOT / "build" / "tetrislab.sym").read_text().splitlines():
        parts = line.split()
        if len(parts) == 2 and ":" in parts[0]:
            bank, addr = parts[0].split(":")
            syms.setdefault(parts[1], (int(bank, 16), int(addr, 16)))
    bank, addr = syms["Gfx_MenuScreens"]
    off = addr if bank == 0 else bank * 0x4000 + addr - 0x4000
    want = rom[off:off + 16]

    with Tetris(ROM) as t:
        # The menu is a screen with artwork of its own now - Tolstoj's sheet,
        # from $27 up, the same slot the title screen's uses. What has to hold
        # is that everything downstream of it puts the menu tileset back.
        t.to_mode(MODE_TETRIS)
        t.press("start")                  # -> the level select
        t.run_until_state(GS_A_TYPE_SELECTION_MAIN)
        t.tick(20)
        got = bytes(t[0x8000 + 0x30 * 16 + i] for i in range(16))
        assert got == want, "the level select is showing another screen's tiles"

        t.press("start")                  # -> the game
        t.run_until_state(GS_IN_GAME_MAIN)
        t.tick(20)
        got = bytes(t[0x8000 + 0x30 * 16 + i] for i in range(16))
        assert got == want, "the game is showing another screen's tiles"


def test_the_menu_header_shows_the_version_the_rom_carries():
    """The layout used to have the version drawn into it, so it was right on the
    day it was cut and stale from the next release. Drawn by code now, the way
    the title screen's is, and right-aligned against the header box's edge so a
    version that grows a character takes a gap cell rather than the edge.
    """
    rom = (ROOT / "build" / "tetrislab.gb").read_bytes()
    syms = {}
    for line in (ROOT / "build" / "tetrislab.sym").read_text().splitlines():
        parts = line.split()
        if len(parts) == 2 and ":" in parts[0]:
            bank, addr = parts[0].split(":")
            syms.setdefault(parts[1], (int(bank, 16), int(addr, 16)))
    bank, addr = syms["LabVersion"]
    off = addr if bank == 0 else bank * 0x4000 + addr - 0x4000
    version = rom[off:off + 40].split(b"\x00")[0].decode().split()[-1]

    EDGE, ROW = 11, 0x9800 + 4 * 32
    tile = {".": 0x24, **{str(d): d for d in range(10)}}
    with Tetris(ROM) as t:
        to_menu(t)
        first = EDGE - len(version)
        got = [t[ROW + first + i] for i in range(len(version))]
        assert got == [tile[c] for c in version], (
            f"the header shows {got}, the ROM says {version}"
        )
        assert t[ROW + EDGE] != tile.get("0"), "the version ran over the box edge"


def test_the_title_screen_shows_the_version_the_rom_carries():
    """The version is drawn over the artwork rather than stored in it, so a
    release bumps LAB_VERSION and nothing else - no new layout from the artist.

    The artwork leaves five cells between "VERSION" and the box's right edge at
    column 16, and the number is right-aligned against that edge - so a version
    that grows a character takes a gap cell rather than the edge tile. Written
    down as column 13 rather than derived, `0.10` drew its last digit over the
    edge and the box lost its right-hand side.

    This asserts the ROM's string and the screen agree, wherever the string's
    length puts it.
    """
    rom = (ROOT / "build" / "tetrislab.gb").read_bytes()
    syms = {}
    for line in (ROOT / "build" / "tetrislab.sym").read_text().splitlines():
        parts = line.split()
        if len(parts) == 2 and ":" in parts[0]:
            bank, addr = parts[0].split(":")
            syms.setdefault(parts[1], (int(bank, 16), int(addr, 16)))
    bank, addr = syms["LabVersion"]
    off = addr if bank == 0 else bank * 0x4000 + addr - 0x4000
    text_ = rom[off:off + 40].split(b"\x00")[0].decode()
    version = text_.split()[-1]
    assert len(version) <= 5, (
        f"{version!r} is {len(version)} characters; the field is five cells"
    )

    EDGE, ROW = 16, 0x9800 + 11 * 32
    # 0-9 are tiles $00-$09 and "." is $24, so the cells are the string itself
    tile = {".": 0x24, **{str(d): d for d in range(10)}}
    want = [tile[c] for c in version]
    with Tetris(ROM) as t:
        t.to_title()
        t.tick(20)
        first = EDGE - len(version)
        got = [t[ROW + first + i] for i in range(len(version))]
        assert got == want, (
            f"the screen shows {got}, the ROM says {version} = {want}"
        )
        assert t[ROW + EDGE] == 0x91, (
            "the version ran over the box's right edge"
        )
        assert t[ROW + first - 1] == 0x32, (
            "the version is not right-aligned against the edge"
        )


def test_the_menu_borrows_the_originals_arrow_for_its_cursor():
    """The menu's tileset has no arrow in it - the one the original marks a
    selection with lives in the title-screen tileset - so the menu copies that
    single tile into $FF. Read out of VRAM, because the tilemap only says which
    tile index is drawn, not what is in it.

    The title screen needs none of this: Tolstoj drew an arrow into the artwork,
    and selecting a side moves that tile.
    """
    want = (ROOT / "build" / "obj" / "build" / "titleScreen.2bpp").read_bytes()
    want = want[(0x58 - 0x27) * 16:][:16]

    with Tetris(ROM) as t:
        t.to_menu()
        got = bytes(t[0x8000 + 0xFF * 16 + i] for i in range(16))
        assert got == want, "the menu has no arrow tile"

        # A sprite, not a cell in the map. The list scrolls under the cursor, so
        # a background arrow would scroll with it and would have to be erased
        # and redrawn on every move.
        assert t[0xFE02] == 0xFF, "the menu cursor sprite is not the arrow"
        assert t[0xFE00] != 0, "the menu cursor sprite is hidden"


def test_the_title_screen_has_exactly_one_cursor():
    """The artwork carries an arrow beside 1 PLAYER, so a sprite on top of it is
    a second cursor - both drawn, only one of them moving. Selecting a side
    moves the artwork's own tile and nothing else."""
    with Tetris(ROM) as t:
        t.to_title()
        t.tick(20)
        one, two = 0x9800 + 15 * 32, 0x9800 + 15 * 32 + 10
        assert (t[one], t[two]) == (0x9C, 0x32), "1 PLAYER should start selected"
        assert not any(t[0xC000 + i * 4] for i in range(40)), (
            "a sprite is drawn over the artwork's own cursor"
        )
        t.press("right")
        assert (t[one], t[two]) == (0x32, 0x9C), "the arrow did not move to 2 PLAYER"
        t.press("left")
        assert (t[one], t[two]) == (0x9C, 0x32), "the arrow did not move back"


def test_left_and_right_choose_a_side_rather_than_toggling():
    """How the original reads this screen ($04A7): Left and Right each choose
    one side, and pressing for the side already chosen does nothing. Select is
    the thing that flips.

    Treating either direction as a flip is worse than untidy - a double-tap of
    Right launches a one-player game, and a double-tap of Left opens the link
    handshake, which busy-waits for a partner that is not there.
    """
    one, two = 0x9800 + 15 * 32, 0x9800 + 15 * 32 + 10

    with Tetris(ROM) as t:
        t.to_title()
        t.tick(20)
        assert t[hIs2Player] == 0, "should open on 1 PLAYER"

        t.press("right")
        assert t[hIs2Player] == 1, "Right should choose 2 PLAYER"
        t.press("right")
        assert t[hIs2Player] == 1, "a second Right must not send it back"

        t.press("left")
        assert t[hIs2Player] == 0, "Left should choose 1 PLAYER"
        t.press("left")
        assert t[hIs2Player] == 0, "a second Left must not send it back"

        t.press("select")
        assert t[hIs2Player] == 1, "Select flips"
        t.press("select")
        assert t[hIs2Player] == 0, "and flips back"

        assert (t[one], t[two]) == (0x9C, 0x32), "the arrow disagrees with the side"


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
    """B goes to $08, which paints the menu - the screen it came from."""
    with Tetris(ROM) as t:
        t.to_level_select()
        t.press("b")
        t.tick(60)
        assert t.state == GS_GAME_TYPE_MAIN, f"landed on state ${t.state:02X}"


def test_the_menu_replaces_the_game_type_screen():
    with Tetris(ROM) as t:
        to_menu(t)
        # The whole map, not the visible window: the list is 32 rows and the
        # TRAINING section is below the fold until you scroll to it.
        rows = [text(t, r) for r in range(32)]
        joined = "\n".join(rows)
        for want in ("TETRIS", "LAB", "B-TYPE", "STANDARD", "COMPETITION",
                     "TRAINING", "TRANSITION", "SEED", "MUSIC"):
            assert want in joined, f"{want!r} missing from the menu:\n{joined}"
        assert "PLAYER" not in joined, (
            "2 PLAYER belongs on the title screen, not the menu")


def test_the_list_scrolls_once_the_selection_passes_the_middle():
    """The list is 32 rows and the screen shows 18, so it has to move under the
    cursor. Nothing scrolls while the selection is in the top half; below that
    the selected row is pinned to the anchor and the map slides instead.

    This only works because VBlank no longer zeroes the scroll register every
    frame - see deviation #23. Without that hook the cursor pins correctly and
    the picture never moves, which is exactly how the need for it showed.
    """
    ANCHOR, rSCY = 15, 0xFF42
    with Tetris(ROM) as t:
        to_menu(t)
        seen = []
        for _ in range(len(MENU_MAP_ROWS)):
            row = MENU_MAP_ROWS[t[wLabMode]]
            want = max(0, row - ANCHOR) * 8
            seen.append((row, t[rSCY], want))
            t.press("down")

    for row, got, want in seen:
        assert got == want, f"map row {row}: SCY {got}, wanted {want}"
    assert any(s for _, s, _ in seen), "nothing ever scrolled"


def test_the_cursor_follows_the_selection_down_the_screen():
    """The arrow is a sprite, so it has to be placed against the scroll rather
    than drawn into the row. Once the list is scrolling it stops moving and the
    map moves instead."""
    ANCHOR, rSCY = 15, 0xFF42
    with Tetris(ROM) as t:
        to_menu(t)
        for _ in range(len(MENU_MAP_ROWS)):
            row = MENU_MAP_ROWS[t[wLabMode]]
            want = (row * 8 - t[rSCY]) + 16       # OAM counts from off the edge
            assert t[0xFE00] == want, (
                f"map row {row}: cursor at Y {t[0xFE00]}, wanted {want}"
            )
            assert t[0xFE00] <= ANCHOR * 8 + 16, "the cursor ran off the anchor"
            t.press("down")


def test_the_rows_with_nothing_behind_them_are_blank_and_unreachable():
    """Tolstoj's layout draws HZ-DISPLAY, INPUTS, LINE CAP and ELEVATED. None of
    them exists yet, and a row you can see and cannot reach reads as broken - so
    they are wiped at init and left out of the entry table."""
    UNBUILT = (9, 10, 20, 27)
    with Tetris(ROM) as t:
        to_menu(t)
        for row in UNBUILT:
            # Columns 1-18: the box's own sides at 0 and 19 stay.
            inside = text(t, row, range(1, 19))
            assert inside.strip() == "", (
                f"map row {row} still reads {inside!r}"
            )

        reached = {t[wLabMode]}
        for _ in range(30):
            t.press("down")
            reached.add(t[wLabMode])
        assert len(reached) == len(MENU_MAP_ROWS), (
            f"the cursor reached {sorted(reached)}"
        )


def test_the_list_auto_repeats():
    """A twelve-row list is unusable without it. Tolstoj's values: a fresh press
    acts at once, then 24 frames before it repeats and 8 between repeats."""
    with Tetris(ROM) as t:
        to_menu(t)
        start = t[wLabMode]
        t.hold("down")
        t.tick(1)
        assert t[wLabMode] != start, "a fresh press should act immediately"

        moved = t[wLabMode]
        t.tick(20)
        assert t[wLabMode] == moved, "it repeated before the initial delay"
        t.tick(8)
        assert t[wLabMode] != moved, "it never repeated"
        t.release("down")


def test_leaving_the_menu_takes_the_scroll_with_it():
    """VBlank used to clear the scroll register every frame and no longer does,
    so a screen entered from a scrolled list would inherit the scroll. Every
    other screen is drawn expecting none."""
    rSCY = 0xFF42
    with Tetris(ROM) as t:
        to_menu(t)
        goto_row(t, MODE_OBSTACLE)
        assert t[rSCY], "the list should be scrolled on the last row"
        goto_row(t, MODE_TETRIS)
        t.press("start")
        t.run_until_state(GS_A_TYPE_SELECTION_MAIN)
        t.tick(20)
        assert t[rSCY] == 0, f"the level select inherited SCY {t[rSCY]}"


BRIGHT = 0xC6                   # the bright alphabet, one plane lighter


def test_the_bright_alphabet_lands_where_no_screen_draws():
    """It is a copy of the font written straight into VRAM, so it destroys
    whatever tiles it lands on. $A0 looked free from the menu, the level select
    and the game - and was not: the game over screen underlines GAME and OVER
    with $AD, and those two words grew a row of faint Ds. Reported by Giovanni.

    So the screens are walked and asked, rather than three of them being checked
    by hand and the rest assumed.
    """
    used = set()

    def collect(t, skip=()):
        """Every cell of the map, minus the ones the Lab paints in the bright
        alphabet itself - a value blinking is not a collision with it."""
        for r in range(32):
            for c in range(32):
                if (r, c) in skip:
                    continue
                used.add(t[0x9800 + r * 32 + c])

    # The menu's value columns and the level select's picker are where the Lab
    # draws bright glyphs on purpose.
    VALUES = {(r, c) for r in range(32) for c in range(13, 19)}
    PICKER = {(6, 16)}

    with Tetris(ROM) as t:
        t.to_title()
        t.tick(20)
        collect(t)
        to_menu(t)
        collect(t, VALUES)

        goto_row(t, MODE_BTYPE)
        t.press("start")
        t.run_until_state(GS_B_TYPE_SELECTION_MAIN)
        t.tick(20)
        collect(t)
        t.press("b")
        t.run_until_state(GS_GAME_TYPE_MAIN)
        t.tick(20)

        goto_row(t, MODE_TETRIS)
        t.press("start")
        t.run_until_state(GS_A_TYPE_SELECTION_MAIN)
        t.tick(20)
        collect(t, PICKER)
        t.press("start")
        t.run_until_state(GS_IN_GAME_MAIN)
        t.tick(60)
        collect(t)

        t.pb.memory[0xFFE1] = 0x0D                  # game over
        t.run_until(lambda: t.state == 0x04, what="the game over screen")
        t.tick(40)
        collect(t)
        t.press("start")
        t.run_until(lambda: t.state in (0x11, 0x15), what="what follows it")
        t.tick(30)
        collect(t, PICKER)

    # Read out of the ROM, not duplicated here: the first version of this test
    # carried its own copy of the offset and passed against the wrong range
    # while the ROM's had moved.
    rom = (ROOT / "build" / "tetrislab.gb").read_bytes()
    syms = {}
    for line in (ROOT / "build" / "tetrislab.sym").read_text().splitlines():
        parts = line.split()
        if len(parts) == 2 and ":" in parts[0]:
            bank, addr = parts[0].split(":")
            syms.setdefault(parts[1], (int(bank, 16), int(addr, 16)))
    bank, addr = syms["LabBrightBase"]
    base = rom[addr if bank == 0 else bank * 0x4000 + addr - 0x4000]

    block = range(base, base + 0x26)
    clash = sorted(v for v in used if v in block)
    assert not clash, (
        f"the bright alphabet at ${base:02X} sits on tiles the game draws: "
        f"{[hex(v) for v in clash]}"
    )


def test_the_bright_alphabet_is_the_dark_one_with_a_plane_cleared():
    """Tolstoj's trick, and it costs no artwork: a tile row is two bytes, the
    low bitplane then the high one, so keeping the first and zeroing the second
    leaves the glyph in the light shade instead of the darkest."""
    with Tetris(ROM) as t:
        to_menu(t)
        for tile in (0x00, 0x05, 0x0A, 0x19, 0x25):     # digits, letters, dash
            dark = [t[0x8000 + tile * 16 + i] for i in range(16)]
            lit = [t[0x8000 + (BRIGHT + tile) * 16 + i] for i in range(16)]
            assert lit[0::2] == dark[0::2], f"tile ${tile:02X} lost its glyph"
            assert set(lit[1::2]) == {0}, f"tile ${tile:02X} kept both planes"


def test_only_the_selected_rows_value_blinks():
    """The label stays put and every other row stays dark, so leaving a row puts
    its value back to black by itself - the next frame paints it dark."""
    VALUES = {MODE_TRANSITION: 24, MODE_CRUNCH: 25, MODE_OBSTACLE: 26}
    with Tetris(ROM) as t:
        to_menu(t)
        goto_row(t, MODE_CRUNCH)
        seen = {row: set() for row in VALUES.values()}
        labels = set()
        for _ in range(40):
            t.tick(1)
            for row in VALUES.values():
                seen[row].add(t[0x9800 + row * 32 + 13])
            labels.add(text(t, 25, range(2, 12)))

        assert len(seen[25]) == 2, f"CRUNCH's value did not blink: {seen[25]}"
        assert any(v >= BRIGHT for v in seen[25]), "it blinked, but not bright"
        for row in (24, 26):
            assert all(v < BRIGHT for v in seen[row]), (
                f"map row {row} blinked and it is not the selected one"
            )
        assert len(labels) == 1, f"the label blinked too: {labels}"


def test_only_the_seed_digit_being_edited_blinks():
    """The whole value pulsing would lose the digit you are changing inside it."""
    with Tetris(ROM) as t:
        to_menu(t)
        goto_row(t, MODE_SEED)
        t.press("a")
        seen = set()
        for _ in range(40):
            t.tick(1)
            seen.add(tuple(t[0x9800 + 19 * 32 + 13 + i] for i in range(6)))

        assert len(seen) == 2, f"the seed row did not blink: {seen}"
        first = {row[0] for row in seen}
        rest = {v for row in seen for v in row[1:]}
        assert any(v >= BRIGHT for v in first), "the active digit stayed dark"
        assert all(v < BRIGHT for v in rest), "a digit other than the active one blinked"


def test_the_music_row_spells_its_value_out():
    """Six cells, because the layout gives the row six. A single letter beside a
    baked "-TYPE" is only right by accident - it read "--TYPE" with music off."""
    with Tetris(ROM) as t:
        to_menu(t)
        got = []
        for _ in range(4):
            # Read from another row: on MUSIC the value is blinking, and half
            # the frames it is in the bright alphabet.
            goto_row(t, MODE_TETRIS)
            got.append(text(t, 8, range(13, 19)))
            goto_row(t, MODE_MUSIC)
            t.press("right")
        assert got == ["A-TYPE", "B-TYPE", "C-TYPE", "OFF"], got


def test_only_glyphs_are_brightened():
    """The bright block is a copy of the font and stops where the font does, so
    shifting anything else into it lands on whatever tile sits at that index.
    MUSIC pads "OFF" out to six cells with blanks, and each of those blinked
    into a different piece of the artwork. Reported by Giovanni.
    """
    FONT_TILES, BLANK = 0x26, 0x2F
    with Tetris(ROM) as t:
        to_menu(t)
        goto_row(t, MODE_MUSIC)
        for _ in range(3):
            t.press("right")              # A -> B -> C -> OFF

        seen = set()
        for _ in range(40):
            t.tick(1)
            seen.add(tuple(t[0x9800 + 8 * 32 + 13 + i] for i in range(6)))

        assert len(seen) == 2, f"OFF did not blink: {seen}"
        for row in seen:
            for cell in row:
                ok = (cell < FONT_TILES                       # a glyph
                      or BRIGHT <= cell < BRIGHT + FONT_TILES  # a bright glyph
                      or cell == BLANK)
                assert ok, f"${cell:02X} is none of those: {row}"
            assert row[3:] == (BLANK, BLANK, BLANK), (
                f"the padding was brightened: {row}"
            )


def test_the_menu_comes_back_where_you_left_it():
    """The loop is "set it up, try it, come back and change it", so starting
    from the top of a twelve-row list every time makes its length the price of
    that. The row survives in WRAM and the scroll is derived from it, so the
    cursor and the view come back together.

    A cold boot zeroes the row, which is the first entry - asserted here too,
    because "remembers where it was" must not mean "opens somewhere arbitrary".
    """
    rSCY = 0xFF42
    with Tetris(ROM) as t:
        to_menu(t)
        assert t[wLabMode] == MODE_MUSIC, "a fresh boot should open on the first row"
        assert t[rSCY] == 0, "and unscrolled"

        for mode in (MODE_OBSTACLE, MODE_CRUNCH, MODE_TETRIS):
            goto_row(t, mode)
            was = (t[wLabMenuRow], t[rSCY], t[0xFE00])
            t.press("start")
            t.run_until_state(GS_A_TYPE_SELECTION_MAIN)
            t.tick(20)
            assert t[rSCY] == 0, "the level select inherited the menu's scroll"

            t.press("b")                        # back to the menu
            t.run_until_state(GS_GAME_TYPE_MAIN)
            t.tick(20)
            now = (t[wLabMenuRow], t[rSCY], t[0xFE00])
            assert now == was, (
                f"mode {mode}: left on row/SCY/cursor {was}, came back to {now}"
            )


def test_launching_shows_no_screen_in_between():
    """Reported by Giovanni: "it flashes a screen that i cannot recognise".

    The tileset changes on the way to the level select, and for one lit frame
    the menu's own map was still up underneath it - the list drawn in the level
    select's alphabet. Every fix short of the right one moved that frame rather
    than removing it: blanking the map hid it, and loading the tileset one state
    later moved it out of the window the first version of this test watched.

    So the frames are watched all the way to the destination, and the property
    is that map and tiles never disagree: while the menu's layout is on screen
    the menu's tileset is loaded, or the screen is dark.
    """
    LCDCF_ON = 0x80
    for mode, state in ((MODE_TETRIS, GS_A_TYPE_SELECTION_MAIN),
                        (MODE_BTYPE, GS_B_TYPE_SELECTION_MAIN),
                        (MODE_OBSTACLE, GS_A_TYPE_SELECTION_MAIN)):
        with Tetris(ROM) as t:
            to_menu(t)
            goto_row(t, mode)
            menu = bytes(t[0x8000 + 0x30 * 16 + i] for i in range(16))
            scroll = t[0xFF42]
            # Pressed by hand rather than with press(), which ticks four frames
            # of its own - the jump happens on the first of them, and an earlier
            # version of this test started watching after it.
            t.pb.button_press("start")

            for _ in range(90):
                t.tick(1)
                if t[0xFF40] & LCDCF_ON:
                    tiles = bytes(t[0x8000 + 0x30 * 16 + i] for i in range(16))
                    menus_map = "STANDARD" in text(t, 12)
                    assert menus_map == (tiles == menu), (
                        f"mode {mode}: a lit frame had "
                        + ("the menu's map under another screen's tiles"
                           if menus_map
                           else "the menu's tileset under another screen's map")
                    )
                    # And the view does not jump before it goes dark. Resetting
                    # the scroll for the next screen while this one is still lit
                    # snaps the list to its top - only visible from a row far
                    # enough down to have scrolled, which is why it outlived
                    # three passes at this test.
                    if menus_map:
                        assert t[0xFF42] == scroll, (
                            f"mode {mode}: the list jumped from SCY {scroll} "
                            f"to {t[0xFF42]} while still on screen"
                        )
                if t.state == state:
                    break
            else:
                raise AssertionError(f"mode {mode}: never reached ${state:02X}")
            t.pb.button_release("start")


def test_the_menu_has_exactly_one_cursor():
    """Tolstoj draws the cursor into his layouts - on the title screen the
    artwork's own arrow is the cursor and there is no sprite. Here it sits baked
    at the MUSIC row and cannot move, because the list scrolls under the cursor
    and a cell in the map scrolls with the list. Two arrows, one of them inert.

    Reported by Giovanni: "There is a fixed > that stays at Music and does not
    move." The title screen had the same bug, from the same cause.
    """
    TILE_CURSOR, COL = 0x58, 1
    with Tetris(ROM) as t:
        to_menu(t)
        drawn = [r for r in range(32)
                 if t[0x9800 + r * 32 + COL] == TILE_CURSOR]
        assert not drawn, f"the map still draws a cursor on rows {drawn}"

        # And the sprite sits in that column rather than on the label, which is
        # what the second arrow overlapped. His X is already an OAM coordinate.
        for mode in (MODE_MUSIC, MODE_TETRIS, MODE_OBSTACLE):
            goto_row(t, mode)
            assert t[0xFE01] == 0x10, (
                f"mode {mode}: cursor at OAM X {t[0xFE01]}, wanted $10"
            )


def test_the_menu_draws_in_its_own_tileset():
    """The layout indexes 44 tiles of Tolstoj's artwork above the font - the box,
    the frame, the section rules. Every tileset shares the alphabet, so a menu
    without his sheet reads back perfectly from the tilemap and is drawn entirely
    in the wrong furniture. That is how it shipped to Giovanni: "the menu scrolls
    but it's full of garbage"."""
    sheet = (ROOT / "build" / "obj" / "build" / "labMenuTiles.2bpp").read_bytes()
    layout = (ROOT / "src" / "lab" / "data" / "labMenuMap.bin").read_bytes()
    art = sorted({v for v in layout if v > 0x25})
    assert len(art) > 40, f"only {len(art)} artwork tiles - did the layout change?"

    FIRST = 0x27
    with Tetris(ROM) as t:
        to_menu(t)
        for tile in art:
            off = (tile - FIRST) * 16
            want = sheet[off:off + 16]
            got = bytes(t[0x8000 + tile * 16 + i] for i in range(16))
            assert got == want, f"tile ${tile:02X} is not the menu's own"


def test_both_level_selects_load_their_own_tileset():
    """GameState08_GameMusicTypeInit ($1452) was the only place in the ROM that
    loaded this tileset, and every screen after it inherited. The Lab menu
    replaced that screen and loads Tolstoj's artwork instead, so each screen
    downstream has to fetch its own - B-type's level select is hooked for
    nothing else.

    And the LCD goes back on with it: loading a tileset turns it off, and the
    original's init opens with TurnOffLCD, which waits for a VBlank an already
    dark LCD will never send. That hung the level select's init with a black
    screen and nothing to say why.
    """
    want = None
    with Tetris(ROM) as t:
        to_menu(t)
        for mode, state in ((MODE_TETRIS, GS_A_TYPE_SELECTION_MAIN),
                            (MODE_BTYPE, GS_B_TYPE_SELECTION_MAIN)):
            goto_row(t, mode)
            t.press("start")
            t.run_until_state(state)
            t.tick(20)
            got = bytes(t[0x8000 + 0x30 * 16 + i] for i in range(16))
            if want is None:
                want = got
            assert got == want, f"mode {mode} kept the menu's tiles"
            assert t[0xFF40] & 0x80, "the LCD never came back on"
            t.press("b")                    # back to the menu for the next one
            t.run_until_state(GS_GAME_TYPE_MAIN)
            t.tick(20)


def test_the_cursor_moves_and_wraps():
    """The list opens on its first row, which is MUSIC - Tolstoj's layout puts
    the settings above the modes - and wraps at both ends onto OBSTACLE, which
    is the last entry rather than the last mode number."""
    with Tetris(ROM) as t:
        to_menu(t)
        assert t[wLabMode] == MODE_MUSIC, "should open on the first row"
        t.press("up")
        assert t[wLabMode] == MODE_OBSTACLE, "Up from the first row should wrap"
        t.press("down")
        assert t[wLabMode] == MODE_MUSIC, "Down from the last row should wrap"


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
