#!/usr/bin/env python3
"""SPS - same piece sequence.

    .venv/bin/python tests/test_sps.py

The generator is the community's LFSR, transcribed byte for byte, so that a
given seed produces the same pieces here as on their ROM. For a fairness
mechanism interoperability is the feature; see docs/existing-hacks.md section 4.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.emu import Tetris, sym, hATypeLevel, GS_IN_GAME_MAIN  # noqa: E402
from tools.lfsr import step as lfsr_step  # noqa: E402

ROM = "build/tetrislab.gb"

# The piece being played, as the game itself names it: wSpriteSpecs +
# SPR_SPEC_SpecIdx. Spec indexes are piece * 4 + rotation, so the low two bits
# are the rotation and the piece is the rest.
wCurrPieceSpec = 0xC203
PIECE = 0xFC
wLabRngHi, wLabRngMid, wLabRngLo = sym("wLabRngHi"), sym("wLabRngMid"), sym("wLabRngLo")
wLabSeedHi, wLabSeedMid, wLabSeedLo = sym("wLabSeedHi"), sym("wLabSeedMid"), sym("wLabSeedLo")
GS_IN_GAME_INIT = 0x0A
hLabSpsEnabled = 0xFFFE
hHiddenLoadedPiece = 0xFFAE
rDIV = 0xFF04

# The retry loop draws up to three times per piece, so per-frame sampling can
# miss intermediate LFSR steps.
MAX_DRAWS_PER_PIECE = 3


def arm(t, seed):
    t.pb.memory[wLabRngHi] = (seed >> 16) & 0xFF
    t.pb.memory[wLabRngMid] = (seed >> 8) & 0xFF
    t.pb.memory[wLabRngLo] = seed & 0xFF
    t.pb.memory[hLabSpsEnabled] = 1


def rng(t):
    return (t[wLabRngHi] << 16) | (t[wLabRngMid] << 8) | t[wLabRngLo]


def piece_sequence(seed, frames=3000):
    """The pieces a seed deals, from the level select rather than mid-game.

    Arming the LFSR after play has started leaves the pieces before it coming
    from rDIV, and the retry loop compares each new draw against the piece
    already down ($205B) - so those unseeded pieces decide how many times the
    generator draws for the seeded ones. The sequence stays deterministic, but
    it is deterministic in the cycle timing of whatever build is running, and
    the game tops itself out at a different piece each time the ROM moves.
    Seeding the game at its init is what a player does anyway.
    """
    with Tetris(ROM) as t:
        t.to_level_select()
        t.pb.memory[wLabSeedHi] = (seed >> 16) & 0xFF
        t.pb.memory[wLabSeedMid] = (seed >> 8) & 0xFF
        t.pb.memory[wLabSeedLo] = seed & 0xFF
        t.pb.memory[hATypeLevel] = 9
        t.press("start")
        t.run_until_state(GS_IN_GAME_MAIN)
        seq, last = [], t[hHiddenLoadedPiece]
        for _ in range(frames):
            t.tick(1)
            v = t[hHiddenLoadedPiece]
            if v != last:
                seq.append(v)
                last = v
        return seq


def test_the_same_seed_gives_the_same_pieces():
    a = piece_sequence(0x11998F)
    b = piece_sequence(0x11998F)
    assert len(a) >= 8, f"only {len(a)} pieces observed"
    assert a == b, f"not deterministic:\n  {a}\n  {b}"


def test_different_seeds_give_different_pieces():
    a = piece_sequence(0x11998F)
    b = piece_sequence(0x27D844)
    assert a != b, "two seeds produced the same sequence"


def test_the_rom_steps_the_lfsr_the_way_the_model_does():
    """Every state the ROM reaches must appear, in order, in the model's own
    sequence - allowing for steps we cannot see, since the retry loop can draw
    up to three times inside a single frame.

    tests/test_lfsr_vectors.py is what says the model is Toni's. This is what
    says the assembly is the model.
    """
    seed = 0x11998F
    state = seed
    model = []
    for _ in range(200):
        state, _ = lfsr_step(state)
        model.append(state)

    with Tetris(ROM) as t:
        t.start_game_at(9)
        t.tick(30)
        arm(t, seed)
        seen, last = [], rng(t)
        for _ in range(3000):
            t.tick(1)
            cur = rng(t)
            if cur != last:
                seen.append(cur)
                last = cur

    assert len(seen) >= 8, f"only {len(seen)} states observed"
    i = 0
    for state in seen:
        gap = 0
        while i < len(model) and model[i] != state:
            i += 1
            gap += 1
            assert gap <= MAX_DRAWS_PER_PIECE, (
                f"state ${state:06X} is not the model's next (searched {gap} ahead)"
            )
        assert i < len(model), f"state ${state:06X} never occurs in the model"
        i += 1


def test_sps_off_leaves_the_original_generator_alone():
    """With SPS disabled the LFSR must not run at all - pieces come from rDIV,
    as they always did.

    Note this cannot be shown by comparing two runs: the emulator is
    deterministic, so rDIV yields the same values at the same cycle counts and
    identical runs look "seeded". Assert instead that the LFSR state never
    advances, which is only true if the rDIV branch is being taken.
    """
    with Tetris(ROM) as t:
        t.start_game_at(9)
        assert t[hLabSpsEnabled] == 0, "SPS should default to off"
        before = rng(t)
        pieces, last = 0, t[hHiddenLoadedPiece]
        for _ in range(3000):
            t.tick(1)
            v = t[hHiddenLoadedPiece]
            if v != last:
                pieces += 1
                last = v
        # nothing plays the pieces, so the stack tops out after about seven and
        # the game ends. That is plenty to prove the generator ran; the point of
        # the guard is only that it ran at all.
        assert pieces >= 5, f"only {pieces} pieces drawn; the test proves nothing"
        assert rng(t) == before, (
            "the LFSR advanced while SPS was off - the rDIV branch is not taken"
        )


def test_a_seed_of_zero_means_no_seed():
    """$0000 is spent as the "off" value rather than left as a trap.

    It is also a degenerate LFSR state - period 1, every draw returns zero - so
    the community's ROM, which offers it as a default and does not guard it, can
    reach it. Ours cannot: zero disarms SPS and pieces come from rDIV, which is
    genuinely random. That is why there is no "randomise" button.
    """
    state = 0
    for _ in range(5):
        state, _ = lfsr_step(state)
        assert state == 0, "the model should confirm $000000 is a fixed point"

    with Tetris(ROM) as t:
        t.to_level_select()
        for addr in (wLabSeedHi, wLabSeedMid, wLabSeedLo):
            t.pb.memory[addr] = 0
        t.pb.memory[hATypeLevel] = 9
        t.press("start")
        t.run_until_state(GS_IN_GAME_MAIN)
        assert t[hLabSpsEnabled] == 0, "a zero seed should leave SPS off"


def test_the_seed_is_reloaded_at_the_start_of_every_game():
    """A restart must repeat the sequence, not continue it."""
    def lfsr_at_init(t, limit=200):
        seen = []
        for _ in range(limit):
            t.tick(1)
            if t.state == GS_IN_GAME_INIT:
                seen.append(rng(t))
                if len(seen) >= 3:
                    break
        return seen

    with Tetris(ROM) as t:
        t.to_level_select()
        t.pb.memory[wLabSeedHi] = 0x11
        t.pb.memory[wLabSeedMid] = 0x99
        t.pb.memory[wLabSeedLo] = 0x8F
        t.pb.memory[hATypeLevel] = 9
        t.press("start")
        t.run_until_state(GS_IN_GAME_MAIN)
        t.tick(600)
        assert rng(t) != 0x11998F, "the LFSR should have advanced during play"

        for b in ("a", "b", "select", "start"):
            t.pb.button_press(b)
        seen = lfsr_at_init(t)
        for b in ("a", "b", "select", "start"):
            t.pb.button_release(b)
        assert 0x11998F in seen, (
            f"seed not reloaded on restart; saw {[hex(v) for v in seen]}"
        )


def test_the_same_seed_deals_the_same_sequence_after_a_game():
    """Reloading the LFSR is not enough. The generator draws again when a piece's
    top six bits match the last one's ($205B), and that test reads
    hHiddenLoadedPiece, which nothing resets between games. Left over from a
    previous game it costs an extra draw on the first piece and shifts the whole
    sequence by one - so the same seed dealt differently depending on what you
    played before it. Reported by Tolstoj, 2026-08-21."""
    def seeded_game(play_first):
        t = Tetris(ROM)
        t.to_menu()
        for _ in range(5):
            t.press("down")                    # SEED
        t.press("a")
        for nibble in (0x1, 0x1, 0x9, 0x9, 0x8, 0xF):
            for _ in range(nibble):
                t.press("up")
            t.press("right")
        t.press("a")
        for _ in range(5):
            t.press("up")                      # back to TETRIS
        t.press("start")
        t.run_until_state(0x11)
        t.tick(20)
        t.press("start")
        t.run_until_state(GS_IN_GAME_MAIN)
        if play_first:
            t.tick(1500)                       # dirty the generator's state
            for b in ("a", "b", "select", "start"):
                t.pb.button_press(b)
            t.tick(4)
            for b in ("a", "b", "select", "start"):
                t.pb.button_release(b)
            t.run_until_state(GS_IN_GAME_MAIN)
        t.tick(4)
        seen, last = [], None
        for _ in range(4000):
            t.pb.tick()
            cur = t[wCurrPieceSpec] & PIECE
            if cur != last:
                seen.append(cur)
                last = cur
                if len(seen) >= 8:
                    break
        t.close()
        return seen

    fresh, after = seeded_game(False), seeded_game(True)
    assert fresh == after, (
        f"the same seed dealt differently after a game:\n  {fresh}\n  {after}"
    )


def test_seed_can_be_entered_from_the_menu():
    """The SEED row of the Lab menu: A opens the digits, Left/Right pick one,
    Up/Down change it. See docs/decisions/0007."""
    with Tetris(ROM) as t:
        t.to_menu()
        for _ in range(5):
            t.press("down")                    # TETRIS -> ... -> SEED
        t.press("a")                           # open the digits
        for nibble in (0x1, 0x1, 0x9, 0x9, 0x8, 0xF):
            for _ in range(nibble):
                t.press("up")
            t.press("right")
        t.press("a")                           # close them
        for _ in range(5):
            t.press("up")                      # back up to TETRIS
        seed = (t[wLabSeedHi] << 16) | (t[wLabSeedMid] << 8) | t[wLabSeedLo]
        assert seed == 0x11998F, f"typed $11998F, got ${seed:06X}"

        t.press("start")                       # TETRIS -> the level select
        t.run_until_state(0x11)
        t.tick(6)
        t.press("start")
        t.run_until_state(GS_IN_GAME_MAIN)
        assert t[hLabSpsEnabled] != 0, "a non-zero seed should arm SPS"


def test_every_mode_deals_the_same_sequence_for_a_seed():
    """A seed has to mean one sequence, whatever you are playing.

    That is the whole point of SPS: two people race the same pieces, and it is
    worthless if TETRIS and CRUNCH disagree. It holds because the seed is armed
    at the game init every mode passes through, and because no trainer draws
    from the generator - the transition trainer sets counters, crunch writes the
    collision buffer, neither takes a piece.

    Nothing enforces that, which is why this test exists. A future trainer that
    spawns or consumes a piece would desync the modes silently, and a seeded
    sequence that is only right in one mode is worse than no seed at all.
    """
    from tools.emu import GS_A_TYPE_SELECTION_MAIN, hATypeLevel
    # OBSTACLE is not here, and cannot be: it deals an I every time by design, so
    # its sequence is a constant rather than the seed's. The invariant it has to
    # keep instead is that it takes nothing from the generator - which it does
    # not, having replaced the generator's output rather than drawn from it.
    MODES = {"TETRIS": 0, "TRANSITION": 2, "CRUNCH": 3}
    SEED = 0x11998F

    def played(row, frames=3000):
        with Tetris(ROM) as t:
            t.to_menu()
            for _ in range(row):
                t.press("down")
            for _ in range(5):                       # give the row a value
                t.press("right")
            t.pb.memory[wLabSeedHi] = (SEED >> 16) & 0xFF
            t.pb.memory[wLabSeedMid] = (SEED >> 8) & 0xFF
            t.pb.memory[wLabSeedLo] = SEED & 0xFF
            t.press("start")
            t.run_until_state(GS_A_TYPE_SELECTION_MAIN)
            t.tick(20)
            t.pb.memory[hATypeLevel] = 9
            t.press("start")
            t.run_until_state(GS_IN_GAME_MAIN)
            seen, last = [], None
            for _ in range(frames):
                t.tick(1)
                v = t[wCurrPieceSpec] & PIECE
                if v and v != last:
                    seen.append(v)
                    last = v
            return seen

    MINIMUM = 5

    base = played(MODES["TETRIS"])
    assert len(base) >= MINIMUM, (
        f"only saw {len(base)} pieces in TETRIS; the sample is too short to mean anything"
    )
    for name_, row in MODES.items():
        if name_ == "TETRIS":
            continue
        other = played(row)
        # Both sides have to deal a real game. Comparing min(len) alone passes
        # when a mode is broken enough to deal nothing, which is the failure
        # this test is most likely to meet.
        assert len(other) >= MINIMUM, (
            f"{name_} only dealt {len(other)} pieces - it is not playing, "
            f"so nothing here was compared"
        )
        n = min(len(base), len(other))
        assert base[:n] == other[:n], (
            f"{name_} deals a different sequence from TETRIS on the same seed:\n"
            f"  TETRIS {[hex(v) for v in base[:n]]}\n"
            f"  {name_} {[hex(v) for v in other[:n]]}"
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
