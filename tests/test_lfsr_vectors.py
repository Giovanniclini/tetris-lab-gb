#!/usr/bin/env python3
"""The seeded generator must deal what Toni's does.

    .venv/bin/python tests/test_lfsr_vectors.py

Four seeds and the pieces each dealt, recorded from his ROM and sent on
2026-08-22. This is the acceptance test for SPS: a seed is only worth anything
if it means the same thing on both ROMs, so these sequences - not our own
self-consistency - are what says the generator is right.

His dumps are 256-byte buffers holding 255 pieces and a trailing unwritten $00.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.lfsr import stream, step, MASK, PERIOD     # noqa: E402
from tools.pieces import sequence, name               # noqa: E402

VECTORS = ROOT / "tests" / "vectors" / "toni-seeds.txt"
LETTER = {"L": 0x00, "J": 0x04, "I": 0x08, "O": 0x0C,
          "Z": 0x10, "S": 0x14, "T": 0x18}

# Each recording began mid-game, so the piece already loaded and the one hidden
# behind it are part of the vector. Recovered with the sequences themselves.
START = {"11998f": ("T", "S"), "27d844": ("T", "T"),
         "c0e3c6": ("S", "T"), "fb35a8": ("T", "T")}


def vectors():
    out = {}
    for line in VECTORS.read_text().splitlines():
        if line.startswith("#") or not line.strip():
            continue
        seed, pieces = line.split()
        out[seed] = [LETTER[c] for c in pieces]
    return out


def test_every_recorded_seed_deals_the_same_pieces():
    for seed, recorded in vectors().items():
        hidden, loaded = (LETTER[c] for c in START[seed])
        draw = stream(int(seed, 16)).__next__
        dealt = sequence(draw, len(recorded), hidden=hidden, loaded=loaded)
        # the final byte of each dump is an unwritten $00, not a piece
        n = len(recorded) - 1
        assert dealt[:n] == recorded[:n], (
            f"{seed} diverges at piece {next(i for i in range(n) if dealt[i] != recorded[i])}\n"
            f"  recorded {name(recorded[:24])}\n"
            f"  dealt    {name(dealt[:24])}"
        )


def test_the_mask_is_the_only_one_that_fits():
    """$87 was recovered, not given. If a future edit changes it, this says so
    rather than letting seeds silently diverge from his."""
    assert MASK == 0x87, f"the tap mask moved to ${MASK:02X}"


def test_the_period_is_maximal():
    """A short cycle would repeat pieces inside a single game."""
    seed = 0x11998F
    state, n = seed, 0
    while True:
        state, _ = step(state)
        n += 1
        if state == seed or n > PERIOD:
            break
    assert n == PERIOD, f"period is {n:,}, not {PERIOD:,}"


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
