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

from tools.emu import Tetris                        # noqa: E402
from tools.pieces import sequence, name             # noqa: E402
from test_sps import lfsr_step, arm, hHiddenLoadedPiece  # noqa: E402

ROM = "build/tetrislab.gb"
SEEDS = (0xACE1, 0x1234, 0xBEEF)


def predicted(seed, count):
    """What the model says the current 16-bit LFSR deals."""
    hi, lo = seed >> 8, seed & 0xFF

    def draw():
        nonlocal hi, lo
        hi, lo = lfsr_step(hi, lo)
        return lo                                   # LabRandom returns B = the low byte

    return sequence(draw, count)


def observed(seed, frames=6000):
    """What the ROM actually deals. Sampling per frame cannot see a repeat, so
    the model is squashed the same way before comparing."""
    with Tetris(ROM) as t:
        t.start_game_at(9)
        t.tick(30)
        arm(t, seed)
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


def test_the_model_deals_what_the_rom_deals():
    for seed in SEEDS:
        rom = observed(seed)
        assert len(rom) >= 8, f"${seed:04X}: only {len(rom)} pieces seen"
        model = squash(predicted(seed, 400))
        # the first sampled piece may be mid-sequence, so allow a small offset
        assert any(model[o:o + len(rom)] == rom for o in range(3)), (
            f"${seed:04X} diverges\n  rom   {name(rom)}\n  model {name(model[:len(rom)])}"
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
