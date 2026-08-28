#!/usr/bin/env python3
"""B while paused leaves a game for the level select.

    .venv/bin/python tests/test_quit.py

Changing level used to mean topping out on purpose, which is the wrong shape
for a trainer. A+B+Select+Start keeps its own job, so the pair reads as "again"
against "somewhere else".
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.emu import (Tetris, GS_IN_GAME_MAIN,               # noqa: E402
                       GS_A_TYPE_SELECTION_MAIN, hATypeLevel)

ROM = "build/tetrislab.gb"
hGamePaused, hIs2Player = 0xFFAB, 0xFFC5
wScoreBCD = 0xC0A0

MODE_TETRIS, MODE_BTYPE, MODE_TRANSITION, MODE_CRUNCH = 0, 1, 2, 3
A_TYPE_SELECT, B_TYPE_SELECT = 0x11, 0x13


def in_game(row=MODE_TETRIS):
    """A game running, started from `row` of the menu."""
    t = Tetris(ROM)
    t.to_menu()
    for _ in range(row):
        t.press("down")
    if row == MODE_CRUNCH:
        for _ in range(10):
            t.press("right")
    t.press("start")
    if row == MODE_BTYPE:
        t.run_until(lambda: t.state == B_TYPE_SELECT, what="the B-type level select")
        t.press("start")
    else:
        t.run_until_state(GS_A_TYPE_SELECTION_MAIN)
        t.tick(20)
        t.pb.memory[hATypeLevel] = 9
        t.press("start")
    t.run_until_state(GS_IN_GAME_MAIN)
    t.tick(60)
    return t


def test_every_mode_goes_back_to_its_own_level_select():
    """B-type has its own screen; sending a B-type game to the A-type one would
    be the wrong level on the wrong screen. TRANSITION and CRUNCH are A-type
    games, so they land where TETRIS does."""
    for row, want, name in ((MODE_TETRIS, A_TYPE_SELECT, "TETRIS"),
                            (MODE_BTYPE, B_TYPE_SELECT, "B-TYPE"),
                            (MODE_TRANSITION, A_TYPE_SELECT, "TRANSITION"),
                            (MODE_CRUNCH, A_TYPE_SELECT, "CRUNCH")):
        with in_game(row) as t:
            t.press("start")
            t.tick(8)
            assert t[hGamePaused], f"{name} did not pause"
            t.press("b")
            t.tick(40)
            assert t.state == want, (
                f"{name} landed on ${t.state:02X}, wanted ${want:02X}"
            )
            assert not t[hGamePaused], f"{name} arrived still paused"


def test_the_abandoned_score_is_not_filed():
    """Walking out of a game is abandoning it - the same call ADR 0005 makes
    for the half-typed name."""
    with in_game() as t:
        for i, b in enumerate((0x00, 0x50, 0x00)):        # 5000
            t.pb.memory[wScoreBCD + i] = b
        t.press("start")
        t.tick(8)
        t.press("b")
        t.tick(40)
        score = int(f"{t[wScoreBCD+2]:02X}{t[wScoreBCD+1]:02X}{t[wScoreBCD]:02X}")
        assert score == 0, f"the abandoned game still carried {score}"


def test_b_does_nothing_while_the_game_is_running():
    """B rotates. Quitting is only offered from the pause screen, which is the
    one place the game reads neither B nor A."""
    with in_game() as t:
        for _ in range(4):
            t.press("b")
            t.tick(10)
            assert t.state == GS_IN_GAME_MAIN, (
                f"B left the game without a pause: ${t.state:02X}"
            )


def test_the_restart_combination_still_restarts_from_a_pause():
    """B is one quarter of A+B+Select+Start, so a restart pressed while paused
    reaches the quit first. If it wins, the game leaves for the level select and
    then reboots - the combination is still held, and menus reboot (ADR 0005).
    """
    with in_game(MODE_CRUNCH) as t:
        t.press("start")
        t.tick(8)
        assert t[hGamePaused]
        for b in ("a", "b", "select", "start"):
            t.pb.button_press(b)
        t.tick(4)
        for b in ("a", "b", "select", "start"):
            t.pb.button_release(b)
        t.run_until_state(GS_IN_GAME_MAIN)
        t.tick(30)
        assert t.state == GS_IN_GAME_MAIN, f"landed on ${t.state:02X}, not a game"
        assert not t[hGamePaused], "the restarted game is paused"


def test_link_play_cannot_be_abandoned():
    """Quitting one side strands the other mid-game exactly as restarting it
    would, which is why ADR 0005 reboots there instead."""
    with in_game() as t:
        t.press("start")
        t.tick(8)
        t.pb.memory[hIs2Player] = 1
        t.press("b")
        t.tick(30)
        assert t.state == GS_IN_GAME_MAIN, f"link play was abandoned: ${t.state:02X}"
        assert t[hGamePaused], "link play was unpaused by a quit that must not happen"


def test_a_game_can_be_started_again_afterwards():
    """The drill is still selected, so the level select starts the same one."""
    with in_game(MODE_CRUNCH) as t:
        t.press("start")
        t.tick(8)
        t.press("b")
        t.tick(40)
        assert t.state == A_TYPE_SELECT
        t.press("start")
        t.run_until_state(GS_IN_GAME_MAIN)
        t.tick(30)
        row = "".join("#" if t[0x9800 + 10 * 32 + 2 + c] == 0x87 else "."
                      for c in range(10))
        assert row == "##......##", f"crunch did not come back: {row}"


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
