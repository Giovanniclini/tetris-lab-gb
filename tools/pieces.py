"""A model of the original's piece generator, for predicting sequences offline.

`PlayNextPieceLoadNextAndHiddenPiece` ($2011) draws a byte where the stock game
reads rDIV, walks it down to one of seven piece ids, and rejects a draw whose
top six bits match the piece already loaded - up to three tries. The bias that
comes out of that is part of the game and is not ours to fix.

Modelling it here means a candidate randomizer can be checked against a
recorded sequence without running the ROM, which is how the community shares
seeds: as the pieces they deal. test_pieces.py pins the model against the real
ROM so it cannot drift from it.
"""

PIECE_NAMES = {0x00: "L", 0x04: "J", 0x08: "I", 0x0C: "O",
               0x10: "Z", 0x14: "S", 0x18: "T"}


def piece_from_byte(b):
    """The counting loop at $2046: b counts down, a walks 0,4,..,24 and wraps."""
    a = 0
    while True:
        b = (b - 1) & 0xFF
        if b == 0:
            return a
        a += 4
        if a == 0x1C:
            a = 0


def sequence(draw, count, hidden=0, loaded=0):
    """`count` pieces, given `draw()` returning the byte LabRandom puts in B.

    Returns the pieces in the order the game commits them to
    hHiddenLoadedPiece - the same order a dumped sequence records, consecutive
    repeats included.
    """
    out = []
    for _ in range(count):
        tries = 3
        while True:
            drawn = piece_from_byte(draw())
            previous = hidden
            tries -= 1
            if tries == 0:
                break
            # re-draw if the top six bits are unchanged from the loaded piece
            if ((drawn | previous | loaded) & 0xFC) == loaded:
                continue
            break
        hidden, loaded = drawn, previous
        out.append(drawn)
    return out


def name(pieces):
    return "".join(PIECE_NAMES.get(p, "?") for p in pieces)
