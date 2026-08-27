#!/usr/bin/env python3
"""The offline piece-generator model must match the ROM.

    .venv/bin/python tests/test_pieces.py

Seeds are shared in this community as the pieces they deal - Toni sent recorded
sequences for four of them. Checking a randomizer against those means predicting
pieces without running a game, which means modelling the generator. This pins
the model against the real ROM so it cannot quietly drift from it.
"""

import itertools
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from tools.emu import Tetris, GS_IN_GAME_MAIN       # noqa: E402
from tools.pieces import sequence, name             # noqa: E402
from tools.lfsr import stream                       # noqa: E402
from test_sps import (hHiddenLoadedPiece, wLabSeedHi,  # noqa: E402
                      wLabSeedMid, wLabSeedLo)

ROM = "build/tetrislab.gb"
SEEDS = (0x11998F, 0x27D844, 0xC0E3C6)


def predicted(seed, count):
    """What the model says the LFSR deals."""
    return sequence(stream(seed).__next__, count)


def observed(seed, frames=6000):
    """What the ROM actually deals. Sampling per frame cannot see a repeat, so
    the model is squashed the same way before comparing.

    The seed is armed and then the game is restarted, because a piece is always
    already in flight when the seed lands and it was drawn before it. Restarting
    re-arms the seed at the game init and starts the sequence from its first
    piece, so what is sampled is the seeded stream and nothing else.
    """
    with Tetris(ROM) as t:
        t.start_game_at(9)
        t.tick(30)
        t.pb.memory[wLabSeedHi] = (seed >> 16) & 0xFF
        t.pb.memory[wLabSeedMid] = (seed >> 8) & 0xFF
        t.pb.memory[wLabSeedLo] = seed & 0xFF
        for b in ("a", "b", "select", "start"):
            t.pb.button_press(b)
        t.tick(4)
        for b in ("a", "b", "select", "start"):
            t.pb.button_release(b)
        t.run_until_state(GS_IN_GAME_MAIN)
        t.tick(4)
        seen, last = [], t[hHiddenLoadedPiece]
        for _ in range(frames):
            t.tick(1)
            value = t[hHiddenLoadedPiece]
            if value != last:
                seen.append(value)
                last = value
        return seen


def squash(pieces):
    return [p for p, _ in itertools.groupby(pieces)]


def aligns(rom, model, lead=2, start=6):
    """Whether what the ROM dealt appears in the model, in order and unbroken.

    Sampling starts mid-game, so both ends are fuzzy: the piece already in
    flight when the seed is armed was drawn before it and belongs to no seeded
    sequence, and pieces consumed before the first tick are simply missed. So
    up to `lead` leading observations are droppable and the run may begin
    anywhere in the model's first `start` pieces. What is not negotiable is the
    rest: every remaining piece, in order, with no gaps.
    """
    for drop in range(lead + 1):
        tail = rom[drop:]
        if len(tail) < 5:
            break
        if any(model[o:o + len(tail)] == tail for o in range(start)):
            return True
    return False


def test_the_model_deals_what_the_rom_deals():
    for seed in SEEDS:
        rom = observed(seed)
        assert len(rom) >= 5, f"${seed:06X}: only {len(rom)} pieces seen"
        model = squash(predicted(seed, 400))
        assert aligns(rom, model), (
            f"${seed:06X} diverges\n  rom   {name(rom)}\n  model {name(model[:len(rom)])}"
        )


def test_every_draw_yields_one_of_the_seven_pieces():
    from tools.pieces import piece_from_byte, PIECE_NAMES
    for b in range(256):
        assert piece_from_byte(b) in PIECE_NAMES, (
            f"byte ${b:02X} produced ${piece_from_byte(b):02X}, not a piece"
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
