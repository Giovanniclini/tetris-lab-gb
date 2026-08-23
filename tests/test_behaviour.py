#!/usr/bin/env python3
"""Behavioural tests: drive the ROM in an emulator and check what it does.

    .venv/bin/python tests/test_behaviour.py

These complement the byte-level tests. A byte test proves the ROM contains the
right value; these prove the game acts on it. A broken hook can leave every
byte correct.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.emu import Tetris, sym, hIsHardMode, hNumFramesUntilPiecesMoveDown  # noqa: E402

# docs/research.md 2.1 - frames per row for levels 0..20
GRAVITY = [53, 49, 45, 41, 37, 33, 28, 22, 17, 11,
           10, 9, 8, 7, 6, 6, 5, 5, 4, 4, 3]


ROCKETS = {0x58: "big", 0x59: "medium", 0x5A: "small"}
GS_GAME_OVER_CLEARING, GS_PRE_ROCKET_WAIT, GS_LEVEL_ENDED_MAIN = 0x0D, 0x34, 0x04
hATypeRocketSpecIdx = 0xFFF3


def rocket_for(score):
    """Finish a game worth `score` and report which rocket it earns, if any."""
    def bcd(n):
        d = f"{n % 1000000:06d}"
        return [int(d[4:6], 16), int(d[2:4], 16), int(d[0:2], 16)]

    with Tetris("build/tetrislab.gb") as t:
        t.start_game_at(9)
        t.tick(120)
        for i, byte in enumerate(bcd(score)):
            t.pb.memory[0xC0A0 + i] = byte
        t.pb.memory[sym("wLabScoreMillions")] = score // 1000000
        t.pb.memory[0xFFE1] = GS_GAME_OVER_CLEARING
        for _ in range(400):
            t.tick(1)
            if t.state == GS_PRE_ROCKET_WAIT:
                return ROCKETS.get(t[hATypeRocketSpecIdx], "unknown rocket")
            if t.state == GS_LEVEL_ENDED_MAIN:
                return None                      # the plain game over screen
    return "never got anywhere"                  # so a hang cannot read as a pass


def test_gravity_matches_table_for_every_level():
    """The game must actually load the documented gravity for each level.

    Reads the reload value the game computed at gameplay start, for all 21
    levels, by driving the real menus and starting a real game each time.
    """
    with Tetris() as t:
        for level in range(21):
            t.start_game_at(level)
            got = t.gravity()
            assert got == GRAVITY[level], (
                f"level {level}: expected {GRAVITY[level]} frames/row, got {got}"
            )
            t.__init__()  # fresh boot for the next level


def test_hearts_add_ten_levels_and_clamp_at_twenty():
    """docs/research.md 3.7: hard mode is min(level + 10, 20)."""
    with Tetris() as t:
        for level, expected_level in ((0, 10), (5, 15), (9, 19)):
            t.start_game_at(level, hearts=True)
            assert t[hIsHardMode] != 0, f"hard mode not armed for level {level}"
            got = t.gravity()
            assert got == GRAVITY[expected_level], (
                f"heart level {level}: expected level {expected_level} speed "
                f"({GRAVITY[expected_level]} frames/row), got {got}"
            )
            t.__init__()


def test_observed_fall_rate_matches_the_reload_value():
    """Independent check: count actual frames between gravity steps, rather
    than trusting the reload value the game stored."""
    with Tetris() as t:
        t.start_game_at(0)
        expected = t.gravity()
        gaps = t.measure_gravity()
        assert gaps, "no gravity steps observed"
        assert all(g == expected for g in gaps), (
            f"level 0: reload says {expected} frames/row, observed {gaps}"
        )


def test_lab_build_adds_levels_l_and_m():
    """L (21) and M (22) must match KLM exactly: 2 and 1 frames per row.

    M is the engine's ceiling - the gravity counter cannot reload with less
    than one frame - which is why KLM stops there and so do we.
    See docs/existing-hacks.md section 3.
    """
    for level, expected in ((21, 2), (22, 1)):
        with Tetris("build/tetrislab.gb") as t:
            t.start_game_at(level)
            got = t.gravity()
            name = "L" if level == 21 else "M"
            assert got == expected, (
                f"level {name} ({level}): expected {expected} frames/row, got {got}"
            )


def test_lab_build_preserves_every_original_level():
    """Adding L and M must not disturb levels 0-20."""
    with Tetris("build/tetrislab.gb") as t:
        for level in range(21):
            t.start_game_at(level)
            got = t.gravity()
            assert got == GRAVITY[level], (
                f"level {level}: expected {GRAVITY[level]} frames/row, got {got}"
            )
            t.__init__("build/tetrislab.gb")


PIECE_Y = 0xC201                             # wSpriteSpecs[0].BaseYOffset
wScoreBCD = 0xC0A0


def _fall(level, tap_down, frames=900):
    """Most common gap between one-row drops, and the score at the end.

    Down has to be re-pressed for each new piece (wCanPressDownToMakePieceFall),
    so a single hold does nothing after the first one.
    """
    import collections
    with Tetris("build/tetrislab.gb") as t:
        t.start_game_at(level)
        t.tick(60)
        marks, prev = [], t[PIECE_Y]
        for f in range(frames):
            if tap_down:
                if f % 8 == 0:
                    t.pb.button_press("down")
                elif f % 8 == 4:
                    t.pb.button_release("down")
            t.pb.tick()
            cur = t[PIECE_Y]
            if cur == prev + 8:
                marks.append(f)
            prev = cur
        score = int(f"{t[wScoreBCD+2]:02X}{t[wScoreBCD+1]:02X}{t[wScoreBCD]:02X}")
        gaps = [b - a for a, b in zip(marks, marks[1:])]
        return collections.Counter(gaps).most_common(1)[0][0], score


def test_pushdown_still_works_below_l():
    """Pushdown moves the piece every 3 frames, so it is a speed-up everywhere
    the original can reach, and it earns a point per row."""
    free, _ = _fall(9, False)
    pushed, score = _fall(9, True)
    assert pushed < free, f"pushdown did nothing at level 9: {free} -> {pushed}"
    assert score > 0, "no drop points at level 9"


def test_pushdown_does_nothing_at_l_and_m():
    """L and M fall in 2 and 1 frames, so the 3-frame pushdown timer would make
    them *slower* - it hitches instead of accelerating. Tolstoj: "make sure L and
    M do not change their gravity". The drop points go with it: no push, nothing
    to reward."""
    for level, expected in ((21, 2), (22, 1)):
        free, _ = _fall(level, False)
        pushed, score = _fall(level, True)
        assert free == expected, f"level {level} should free-fall in {expected}, got {free}"
        assert pushed == free, (
            f"level {level}: Down changed the fall rate, {free} -> {pushed}"
        )
        assert score == 0, f"level {level} still awarded {score} drop points"


def test_the_real_button_state_is_kept_when_down_is_suppressed():
    """Suppressing pushdown works by editing the controller state the game
    reads, so from that point what the game sees is a lie. Anything that wants
    to *show* the input - toni asked for an input display - has to read the
    unedited copy the Lab keeps."""
    from tools.emu import sym
    hButtonsHeld = 0xFF80
    wLabButtonsHeld = sym("wLabButtonsHeld")

    for level, game_should_see_down in ((9, True), (22, False)):
        with Tetris("build/tetrislab.gb") as t:
            t.start_game_at(level)
            t.tick(60)
            t.pb.button_press("down")
            t.tick(20)
            seen = bool(t[hButtonsHeld] & 0x80)
            stashed = bool(t[wLabButtonsHeld] & 0x80)
            assert seen == game_should_see_down, (
                f"level {level}: game sees Down={seen}, expected {game_should_see_down}"
            )
            assert stashed, f"level {level}: the Lab lost the real button state"


def test_the_score_passes_999999():
    """Three BCD bytes hold six digits, and the original pins them all at $99
    when the add carries out ($0178). That clamp is the ceiling of the storage,
    not a rule - the community competes on KLM's uncapped score."""
    from tools.emu import sym
    wScoreBCD = 0xC0A0
    wLabScoreMillions = sym("wLabScoreMillions")
    BUF, W, EMPTY = 0xC800, 32, 0x2F

    with Tetris("build/tetrislab.gb") as t:
        t.start_game_at(9)
        t.tick(120)
        for i, v in enumerate((0x50, 0x99, 0x99)):      # 999,950
            t.pb.memory[wScoreBCD + i] = v

        for _ in range(1500):                            # wait for a piece to land
            t.pb.tick()
            if any(t[BUF + 17 * W + c] != EMPTY for c in range(2, 12)):
                break
        block = next(t[BUF + 17 * W + c] for c in range(2, 12)
                     if t[BUF + 17 * W + c] != EMPTY)
        for c in range(2, 12):                           # complete the row
            t.pb.memory[BUF + 17 * W + c] = block
            t.pb.memory[0x9800 + 17 * W + c] = block

        for _ in range(900):
            t.pb.tick()
            if t[wLabScoreMillions]:
                break

        score = int(f"{t[wLabScoreMillions]:02X}{t[wScoreBCD+2]:02X}"
                    f"{t[wScoreBCD+1]:02X}{t[wScoreBCD]:02X}")
        assert score > 999999, f"score clamped at {score}"

        t.tick(30)
        # Seven digits at columns 13-19 of both maps: screen 0 for play, screen 1
        # for the pause screen. Column 12 is the box border and stays put.
        for base, which in ((0x9800, "screen 0"), (0x9C00, "screen 1")):
            cells = [t[base + 3 * 32 + 13 + i] for i in range(7)]
            assert cells[0] == t[wLabScoreMillions] & 0x0F, (
                f"{which}: no seventh digit: {[hex(c) for c in cells]}"
            )
            assert all(c <= 9 for c in cells), (
                f"{which}: leading zeros blanked, so the score reads wrong: "
                f"{[hex(c) for c in cells]}"
            )
        assert t[0x9800 + 3 * 32 + 12] == 0x7B, "the score box border was overwritten"


def test_the_rocket_scene_never_plays():
    """The original spends 2.4 seconds waiting and then twenty-odd more on a
    rocket, at exactly the scores a good session produces. A trainer wants the
    drill back. Checked at every threshold the original recognises, and past a
    million, where the score bytes have wrapped."""
    for score in (99999, 100000, 150000, 200000, 999999, 1000000, 9999999):
        assert rocket_for(score) is None, (
            f"{score} still reached the rocket scene"
        )


def test_the_score_is_right_aligned_in_the_spare_cell():
    """The original ends the score at column 18 and leaves 19 blank. Drawing one
    cell right uses that space, and means the number does not shift sideways
    when it gains a seventh digit."""
    with Tetris("build/tetrislab.gb") as t:
        t.start_game_at(9)
        t.tick(200)
        for base in (0x9800, 0x9C00):
            assert t[base + 3 * 32 + 19] <= 9, (
                f"nothing in the spare cell at column 19: ${t[base + 3*32 + 19]:02X}"
            )
            assert t[base + 3 * 32 + 12] == 0x7B, "the box border was overwritten"


def test_the_score_has_an_honest_ceiling():
    """Seven digits is all there is room for - column 11 is inside the playfield
    - so the score pins at 9,999,999 rather than counting into a digit it cannot
    show. Refusing the carry alone is not enough: the add has already wrapped the
    low six, so the score would *fall* from 9,999,950 to 9,000,350."""
    from tools.emu import sym
    wScoreBCD = 0xC0A0
    wLabScoreMillions = sym("wLabScoreMillions")
    BUF, W, EMPTY = 0xC800, 32, 0x2F

    with Tetris("build/tetrislab.gb") as t:
        t.start_game_at(9)
        t.tick(120)
        t.pb.memory[wLabScoreMillions] = 0x09
        for i, v in enumerate((0x50, 0x99, 0x99)):     # 9,999,950
            t.pb.memory[wScoreBCD + i] = v

        for _ in range(1500):
            t.pb.tick()
            if any(t[BUF + 17 * W + c] != EMPTY for c in range(2, 12)):
                break
        block = next(t[BUF + 17 * W + c] for c in range(2, 12)
                     if t[BUF + 17 * W + c] != EMPTY)
        for c in range(2, 12):
            t.pb.memory[BUF + 17 * W + c] = block
            t.pb.memory[0x9800 + 17 * W + c] = block

        for _ in range(900):
            t.pb.tick()
            if t[wScoreBCD + 2] != 0x99:
                break
        t.tick(20)

        score = int(f"{t[wLabScoreMillions]:02X}{t[wScoreBCD+2]:02X}"
                    f"{t[wScoreBCD+1]:02X}{t[wScoreBCD]:02X}")
        assert score == 9999999, f"expected the ceiling, got {score}"


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
