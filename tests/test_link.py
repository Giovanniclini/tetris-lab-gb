#!/usr/bin/env python3
"""Two-player rendezvous, now that the Lab menu has replaced the title screen.

    .venv/bin/python tests/test_link.py

PyBoy's serial is a stub - `set_SB` hard-codes $FF, "connecting is not
implemented yet" - so no real exchange between two units can be emulated here.
What *can* be checked is everything the Lab itself does:

  * that the bytes it puts on the wire are the original's, byte for byte;
  * that it keeps pinging, every frame, from the state the original's serial
    interrupt handler demands;
  * that it reacts correctly to a role being assigned, simulated by writing the
    same HRAM the real handler writes.

What is left untested is the physical exchange, which happens in
SerialInterruptHandler - original code the Lab does not touch. See
docs/decisions/0007.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.emu import Tetris, sym  # noqa: E402

ROM = "build/tetrislab.gb"
STOCK = "build/tetris.gb"

GS_TITLE_SCREEN_MAIN = 0x07
GS_2PLAYER_MUSIC_INIT = 0x2A
GS_2PLAYER_MUSIC_MAIN = 0x2B

rSC = 0xFF02
hMultiplayerPlayerRole = 0xFFCB
hSerialInterruptHandled = 0xFFCC

MP_ROLE_PASSIVE, MP_ROLE_MASTER = 0x55, 0x29
SC_PING = 0x80                       # SC_REQUEST_TRANSFER | SC_PASSIVE

hIs2Player = 0xFFC5


def to_title(t):
    t.run_until_state(GS_TITLE_SCREEN_MAIN)
    t.tick(20)
    return t


def to_two_player(t):
    """2 PLAYER is chosen on the title screen: it is the only state the
    original's serial code assigns a role in."""
    to_title(t)
    t.press("right")
    assert t[hIs2Player] == 1, f"cursor is on side {t[hIs2Player]}, not 2 PLAYER"
    return t


def _find(haystack, needle, start=0x8000):
    i = haystack.find(needle, start)
    assert i >= 0, "sequence not found in the Lab banks"
    return i


def test_the_ping_is_the_originals_bytes():
    """Transcription, not reimplementation: the passive ping the title screen
    sent at $0488 appears verbatim in the Lab's banks."""
    stock = (ROOT / STOCK).read_bytes()
    lab = (ROOT / ROM).read_bytes()
    _find(lab, stock[0x0488:0x0493])


def test_the_master_handshake_is_the_originals_bytes():
    """Likewise for the master's announcement at $04C5."""
    stock = (ROOT / STOCK).read_bytes()
    lab = (ROOT / ROM).read_bytes()
    _find(lab, stock[0x04C5:0x04CD])


def test_boot_goes_straight_to_the_title_screen():
    """The copyright screen is skipped, so the 1P/2P choice is the first thing
    a boot reaches."""
    with Tetris(ROM) as t:
        for frames in range(400):
            t.pb.tick()
            if t.state == GS_TITLE_SCREEN_MAIN:
                break
        else:
            raise AssertionError("never reached the title screen")
        assert frames < 150, f"took {frames} frames ({frames / 59.7:.1f}s)"


def test_the_title_screen_pings_every_frame():
    """A second Game Boy finds us by seeing this. The stock title screen sends
    it every frame; so must whatever replaces that screen."""
    with Tetris(ROM) as t:
        to_title(t)
        for _ in range(60):
            t.pb.tick()
            assert t[rSC] == SC_PING, f"stopped pinging: SC is ${t[rSC]:02X}"


def test_the_stock_title_screen_pings_the_same_way():
    """The comparison that gives the test above its meaning."""
    with Tetris(STOCK) as t:
        t.run_until_state(GS_TITLE_SCREEN_MAIN)
        t.tick(5)
        for _ in range(60):
            t.pb.tick()
            assert t[rSC] == SC_PING, f"stock SC is ${t[rSC]:02X}"


def test_a_partner_joining_starts_two_player_without_a_keypress():
    """The passive half: the master presses Start, our serial handler assigns us
    a role, and the menu has to notice and hand over. Simulated by writing the
    HRAM the real interrupt handler writes."""
    with Tetris(ROM) as t:
        to_title(t)
        t.pb.memory[hMultiplayerPlayerRole] = MP_ROLE_PASSIVE
        t.pb.memory[hSerialInterruptHandled] = 1
        for _ in range(10):
            t.pb.tick()
            if t.state in (GS_2PLAYER_MUSIC_INIT, GS_2PLAYER_MUSIC_MAIN):
                return
        raise AssertionError(f"stayed on the title screen (state ${t.state:02X})")


def test_two_player_with_a_partner_already_found_starts():
    with Tetris(ROM) as t:
        to_two_player(t)
        t.pb.memory[hMultiplayerPlayerRole] = MP_ROLE_MASTER
        t.press("start")
        t.tick(10)
        assert t.state in (GS_2PLAYER_MUSIC_INIT, GS_2PLAYER_MUSIC_MAIN), (
            f"did not reach the 2-player flow (state ${t.state:02X})"
        )


def test_two_player_with_no_cable_stays_on_the_title_screen():
    """The transfer still completes with nothing attached - the byte comes back
    as $FF - so the wait cannot hang, and no role is assigned."""
    with Tetris(ROM) as t:
        to_two_player(t)
        t.pb.memory[hMultiplayerPlayerRole] = 0
        t.press("start")
        t.tick(60)
        assert t.state == GS_TITLE_SCREEN_MAIN, (
            f"went somewhere without a partner (state ${t.state:02X})"
        )
        assert t[hIs2Player] == 1, "the cursor moved on its own"


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
