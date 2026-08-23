"""Toni's 24-bit LFSR, the seeded piece source.

Sent as source on 2026-08-22. His file references `LFSR_MASK_LOW` but does not
define it; $87 was recovered from the four recorded piece sequences he sent with
it - all 1023 written pieces across four seeds, next-best candidate 14 - and
verified maximal, period 16 777 215. Polynomial x^24 + x^7 + x^2 + x + 1.

Not ours, and deliberately so: for a fairness mechanism interoperability is the
feature, so a seed has to deal the same pieces here as on his ROM.
"""

MASK = 0x87
PERIOD = (1 << 24) - 1


def step(state):
    """One step. Returns (new_state, output_byte) - the low byte, after the
    step, which is what the game reads where it used to read rDIV."""
    low = state & 0xFF
    feedback = bin(low & MASK).count("1") & 1
    state = (state >> 1) | (feedback << 23)
    return state, state & 0xFF


def stream(seed):
    """Successive output bytes for a seed, indefinitely."""
    state = seed
    while True:
        state, out = step(state)
        yield out
